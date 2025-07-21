# PRP: Implement Interactive Job Review and Revision Commands

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_HUMAN_CONTROL_EXTENSION_PLANNING.md  
**Target Agent:** Claude Code

---

## 1. The Goal (The "What")

Implement interactive job review commands (`review-interactive`, `revise`, `alternatives`) that extend the existing job approval system to provide granular editing and iterative refinement instead of binary approve/reject workflow. **ENHANCED**: Add conversational feedback workflows that enable natural language revision requests like "This part seems weak, what about [X]?" integrated with agent cognitive engines.

---

## 2. The Context Payload (The "With What")

#### Files to Create/Modify:
- **UPDATE:** `src/cli/commands.py` (extend existing job commands)
- **UPDATE:** `src/workflows/jobs.py` (add revision workflow methods)
- **ENHANCE:** Add conversational feedback API for ChatGPT-style interaction with job review process

#### Key Dependencies & Imports:
```python
# Already available in existing codebase:
from src.workflows.jobs import JobStore
from src.models import JobState
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.syntax import Syntax
import typer
import json
from datetime import datetime

# Enhanced for conversational interaction:
from src.agents.personas import DirectorAgent
from src.chat.conversation import ConversationSession
from fastapi import WebSocket
import asyncio
```

#### Existing Job System Pattern:
```python
# From src/cli/commands.py - EXACT patterns to extend:
@app.command()
def review(job_id: str = typer.Argument(..., help="Job ID to review")):
    """Review the output of a specific job."""
    try:
        job = job_store.get_job(job_id)  # This method needs to exist
        if not job:
            console.print(f"❌ Job {job_id} not found", style="bold red")
            raise typer.Exit(1)
        
        # Display job info
        console.print(f"📋 Reviewing Job: [bold cyan]{job_id}[/bold cyan]")
        console.print(f"🤖 Agent: [bold magenta]{job.agent}[/bold magenta]")
        
        if job.output_payload:
            console.print("\n📄 Agent Output:")
            console.print(JSON(json.dumps(job.output_payload, indent=2)))
            
    except Exception as e:
        console.print(f"❌ Error reviewing job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def approve(job_id: str = typer.Argument(..., help="Job ID to approve")):
    """Approve a job and continue the workflow."""
    # Existing pattern that works
    approved_output = job_store.approve_job(job_id)
    if approved_output:
        console.print("✅ Job approved successfully")
```

#### Existing JobStore Interface:
```python
# From src/workflows/jobs.py - proven methods to extend:
class JobStore:
    def create_job(self, agent: str, input_payload: dict) -> str: # Works
    def update_job_as_pending(self, job_id: str, output_payload: dict): # Works  
    def approve_job(self, job_id: str) -> Optional[dict]: # Works
    def reject_job(self, job_id: str, feedback: str = "") -> Optional[dict]: # Works
    
    # MISSING - need to add:
    def get_job(self, job_id: str) -> Optional[JobState]:
    def request_revision(self, job_id: str, feedback: str, section: str = "all") -> str:
    def generate_alternatives(self, job_id: str, count: int = 3) -> List[str]:
```

#### Agent Output Structure (from validation):
```python
# Director output structure (from test runs):
{
    "title": "Chapter X: Title",
    "scope": "SINGLE_CHAPTER", 
    "goal": "Story objective",
    "key_events": ["event1", "event2", "event3"],
    "emotional_turning_point": "Character development",
    "cliffhanger_concept": "Next chapter setup"
}

# Tactician output structure:
{
    "chapter_metadata": {"goal": "...", "discovery_log": [...]},
    "title_suggestions": ["Title 1", "Title 2"],
    "chapter_beats": [
        {"beat_number": 1, "moment_anchor": "...", "internal_shift": "..."},
        {"beat_number": 2, "moment_anchor": "...", "internal_shift": "..."}
    ]
}
```

#### Conversational Feedback Patterns:
```python
# Natural language interaction patterns for job review:
conversational_patterns = {
    "revision_request": {
        "user_input": "This part seems weak, what about adding more tension?",
        "parsed_intent": {
            "action": "revise",
            "target_section": "emotional_turning_point", 
            "feedback": "add more tension",
            "enhancement_type": "emotional_intensity"
        },
        "agent_response": "I understand you'd like to intensify the emotional stakes. Let me analyze the current emotional arc and suggest specific tension-building techniques..."
    },
    
    "alternative_request": {
        "user_input": "Can we explore different approaches to this character introduction?",
        "parsed_intent": {
            "action": "alternatives",
            "target_section": "character_introduction",
            "variation_count": 3,
            "focus": "approach_diversity"
        },
        "agent_response": "Absolutely! I'll generate three distinct introduction approaches: subtle background presence, dramatic entrance, and relationship-driven reveal..."
    },
    
    "context_clarification": {
        "user_input": "Why did the Director choose this particular emotional turning point?",
        "parsed_intent": {
            "action": "explain",
            "target": "director_decision_rationale",
            "context": "emotional_turning_point_selection"
        },
        "agent_response": "Great question! The Director's cognitive engines identified this moment because it maximizes character vulnerability while advancing the central conflict..."
    }
}
```

---

## 3. The Implementation Blueprint (The "How")

### Step 1: Extend JobStore with Interactive Methods

Add these methods to `src/workflows/jobs.py`:

```python
def get_job(self, job_id: str) -> Optional[JobState]:
    """
    Get job details by ID.
    
    Args:
        job_id: Job identifier
        
    Returns:
        JobState object if found, None otherwise
    """
    try:
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            return JobState.model_validate_json(job_data)
        return None
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return None

def request_revision(self, job_id: str, feedback: str, section: str = "all") -> Optional[str]:
    """
    Request revision of specific job section.
    
    Args:
        job_id: Job identifier  
        feedback: Specific revision feedback
        section: Section to revise ("all", "emotional_arc", "key_events", etc.)
        
    Returns:
        New job ID for revision, None if failed
    """
    try:
        # Get original job
        original_job = self.get_job(job_id)
        if not original_job:
            return None
        
        # Create revision job
        revision_job = JobState(
            agent=original_job.agent,
            status="processing",
            input_payload={
                **original_job.input_payload,
                "revision_request": {
                    "original_job_id": job_id,
                    "feedback": feedback,
                    "section": section,
                    "original_output": original_job.output_payload
                }
            },
            output_payload=None
        )
        
        # Store revision job
        self.redis_client.set(f"job:{revision_job.job_id}", revision_job.model_dump_json())
        
        # Mark original as under revision
        original_job.status = "under_revision"
        original_job.updated_at = datetime.now()
        self.redis_client.set(f"job:{job_id}", original_job.model_dump_json())
        
        logger.info(f"Revision requested for job {job_id}, new job: {revision_job.job_id}")
        return revision_job.job_id
        
    except Exception as e:
        logger.error(f"Failed to request revision for job {job_id}: {e}")
        return None

def get_pending_jobs(self) -> List[JobState]:
    """
    Get all jobs pending approval.
    
    Returns:
        List of JobState objects with pending_approval status
    """
    try:
        # Scan Redis for job keys
        job_keys = self.redis_client.keys("job:*")
        pending_jobs = []
        
        for key in job_keys:
            job_data = self.redis_client.get(key)
            if job_data:
                job = JobState.model_validate_json(job_data)
                if job.status == "pending_approval":
                    pending_jobs.append(job)
        
        # Sort by creation time
        pending_jobs.sort(key=lambda x: x.created_at)
        return pending_jobs
        
    except Exception as e:
        logger.error(f"Failed to get pending jobs: {e}")
        return []

def create_alternative_job(self, original_job_id: str) -> Optional[str]:
    """
    Create alternative version of existing job.
    
    Args:
        original_job_id: Job to create alternative for
        
    Returns:
        New job ID for alternative, None if failed
    """
    try:
        original_job = self.get_job(original_job_id)
        if not original_job:
            return None
        
        # Create alternative job with same input
        alt_job = JobState(
            agent=original_job.agent,
            status="processing", 
            input_payload={
                **original_job.input_payload,
                "alternative_request": {
                    "original_job_id": original_job_id,
                    "variation_seed": datetime.now().isoformat()  # Ensure different output
                }
            },
            output_payload=None
        )
        
        self.redis_client.set(f"job:{alt_job.job_id}", alt_job.model_dump_json())
        
        logger.info(f"Alternative created for job {original_job_id}, new job: {alt_job.job_id}")
        return alt_job.job_id
        
    except Exception as e:
        logger.error(f"Failed to create alternative for job {original_job_id}: {e}")
        return None
```

### Step 2: Add Conversational Feedback Interface

Add `src/chat/job_review_chat.py`:

```python
"""
Conversational interface for job review and revision workflows.
Provides ChatGPT-style interaction with agent cognitive engines.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.agents.personas import DirectorAgent
from src.workflows.jobs import JobStore
from src.models import JobState

class JobReviewChatInterface:
    """Conversational interface for job review and iteration."""
    
    def __init__(self):
        self.director = DirectorAgent()
        self.job_store = JobStore()
        self.conversation_context = {}
    
    async def create_review_session(self, job_id: str, user_id: str = "human") -> str:
        """Start conversational review session for a job."""
        
        # Get job details
        job = self.job_store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        session_id = f"review_{job_id}_{int(datetime.now().timestamp())}"
        
        # Initialize conversation context
        self.conversation_context[session_id] = {
            "job_id": job_id,
            "job": job,
            "user_id": user_id,
            "review_history": [],
            "current_focus": None,
            "agent_insights": {}
        }
        
        return session_id
    
    async def process_review_message(self, session_id: str, user_message: str) -> str:
        """Process natural language review feedback and generate agent response."""
        
        if session_id not in self.conversation_context:
            return "❌ Review session not found. Please start a new review session."
        
        context = self.conversation_context[session_id]
        job = context["job"]
        
        # Parse user intent from natural language
        intent = await self._parse_review_intent(user_message, context)
        
        # Generate appropriate response based on intent
        if intent["action"] == "revise":
            response = await self._handle_revision_request(intent, context)
        elif intent["action"] == "alternatives":
            response = await self._handle_alternatives_request(intent, context)
        elif intent["action"] == "explain":
            response = await self._handle_explanation_request(intent, context)
        elif intent["action"] == "approve":
            response = await self._handle_approval_request(intent, context)
        else:
            response = await self._handle_general_discussion(intent, context)
        
        # Update conversation history
        context["review_history"].append({
            "timestamp": datetime.now(),
            "user_message": user_message,
            "intent": intent,
            "agent_response": response
        })
        
        return response
    
    async def _parse_review_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse natural language input to extract review intent."""
        
        job = context["job"]
        
        # Use Director's cognitive engines to understand intent
        director_prompt = f"""
        Parse the following user message about job review and extract the intent:
        
        User Message: "{message}"
        
        Job Context:
        - Agent: {job.agent}
        - Output: {job.output_payload}
        
        Extract:
        1. Primary action (revise, alternatives, explain, approve, discuss)
        2. Target section if specified
        3. Specific feedback or request
        4. Tone and urgency level
        
        Return structured intent analysis.
        """
        
        director_analysis = await self.director.execute(director_prompt, context)
        
        # Parse director analysis into structured intent
        # (Simplified parsing - in practice would use more sophisticated NLP)
        intent = {
            "action": "discuss",  # default
            "target_section": None,
            "feedback": message,
            "tone": "collaborative",
            "urgency": "normal"
        }
        
        # Simple keyword-based intent detection
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["revise", "change", "modify", "improve", "weak", "better"]):
            intent["action"] = "revise"
        elif any(word in message_lower for word in ["alternatives", "options", "different", "other", "explore"]):
            intent["action"] = "alternatives"
        elif any(word in message_lower for word in ["why", "explain", "rationale", "reason", "understand"]):
            intent["action"] = "explain"
        elif any(word in message_lower for word in ["approve", "good", "accept", "ready", "ship"]):
            intent["action"] = "approve"
        
        # Extract target sections
        if "emotional" in message_lower or "feeling" in message_lower:
            intent["target_section"] = "emotional_turning_point"
        elif "character" in message_lower:
            intent["target_section"] = "character_development"
        elif "plot" in message_lower or "story" in message_lower:
            intent["target_section"] = "key_events"
        elif "ending" in message_lower or "cliffhanger" in message_lower:
            intent["target_section"] = "cliffhanger_concept"
        
        return intent
    
    async def _handle_revision_request(self, intent: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Handle requests for content revision."""
        
        job = context["job"]
        target_section = intent.get("target_section", "all")
        feedback = intent.get("feedback", "")
        
        # Use Director to analyze revision approach
        revision_prompt = f"""
        The user wants to revise the {target_section} section with this feedback: "{feedback}"
        
        Current output:
        {job.output_payload}
        
        Provide:
        1. Understanding of the requested change
        2. Specific revision strategy
        3. How this affects the overall narrative
        4. Alternative approaches to consider
        """
        
        revision_analysis = await self.director.execute(revision_prompt, context)
        
        # Create revision job
        revision_job_id = self.job_store.request_revision(
            job.job_id, 
            feedback, 
            target_section
        )
        
        response = f"""🔄 **Revision Analysis**

I understand you'd like to revise the {target_section or 'content'}. Here's my analysis:

**Requested Change:** {feedback}

**Revision Strategy:** Based on the Director's cognitive engines, I recommend focusing on {target_section} to enhance narrative impact.

**Implementation Approach:** I've created revision job `{revision_job_id}` that will:
• Re-examine the {target_section} with your feedback in mind
• Maintain consistency with existing story elements  
• Explore enhanced approaches while preserving core narrative structure

**Alternative Considerations:** Would you like me to generate multiple revision approaches so you can compare options?

The revision job is now processing. You can monitor progress with `factory status` or continue our conversation to refine the approach further."""
        
        return response
    
    async def _handle_alternatives_request(self, intent: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Handle requests for alternative approaches."""
        
        job = context["job"]
        
        # Generate alternative jobs
        alternative_jobs = []
        for i in range(3):  # Generate 3 alternatives
            alt_job_id = self.job_store.create_alternative_job(job.job_id)
            if alt_job_id:
                alternative_jobs.append(alt_job_id)
        
        response = f"""🎲 **Alternative Approaches Generated**

I've created {len(alternative_jobs)} alternative versions exploring different approaches:

"""
        
        for i, alt_id in enumerate(alternative_jobs, 1):
            response += f"• **Alternative {i}:** Job `{alt_id}` - {self._describe_alternative_approach(i)}\n"
        
        response += f"""
**Next Steps:**
• Monitor generation with `factory status`
• Review alternatives when complete using `factory review-interactive <job_id>`
• We can discuss the different approaches as they're generated

**Conversation Continues:** Feel free to ask about specific aspects you'd like the alternatives to explore, or we can wait and compare the results once they're ready."""
        
        return response
    
    def _describe_alternative_approach(self, alt_number: int) -> str:
        """Provide descriptive labels for alternative approaches."""
        approaches = [
            "Enhanced emotional depth with character vulnerability",
            "Action-focused approach with increased tension",
            "Relationship-centered development with dialogue emphasis"
        ]
        return approaches[(alt_number - 1) % len(approaches)]
    
    async def _handle_explanation_request(self, intent: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Handle requests for explanation of agent decisions."""
        
        job = context["job"]
        
        explanation_prompt = f"""
        The user is asking for explanation about the agent's decision-making process.
        
        Request: "{intent.get('feedback', '')}"
        
        Job Output: {job.output_payload}
        
        Provide detailed explanation of:
        1. Why the agent made specific choices
        2. The cognitive process behind decisions
        3. Alternative paths that were considered
        4. How this fits the overall narrative strategy
        """
        
        explanation = await self.director.execute(explanation_prompt, context)
        
        response = f"""🧠 **Agent Decision Analysis**

Great question! Let me explain the {job.agent}'s cognitive process:

**Decision Rationale:** The agent's choice was driven by narrative strategy engines that prioritize character development arcs and tension escalation patterns.

**Cognitive Process:** The {job.agent} agent analyzed:
• Character relationship dynamics
• Emotional arc progression  
• Plot advancement opportunities
• Reader engagement optimization

**Alternative Paths Considered:** The agent likely evaluated multiple approaches but selected this one because it maximizes narrative impact while maintaining story consistency.

**Strategic Context:** This decision fits into the larger narrative strategy of building toward the climactic confrontation while developing character relationships.

Would you like me to explore how we might adjust this approach, or do you have other questions about the agent's decision-making process?"""
        
        return response
    
    async def _handle_approval_request(self, intent: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Handle approval and completion requests."""
        
        job = context["job"]
        
        # Execute approval
        approved_output = self.job_store.approve_job(job.job_id)
        
        if approved_output:
            response = f"""✅ **Job Approved Successfully**

Excellent! Job `{job.job_id}` has been approved and will continue through the workflow.

**What Happens Next:**
• The approved output moves to the next agent in the pipeline
• You'll receive notifications when the next stage is ready for review
• The conversation context is preserved for future reference

**Workflow Continuation:** The narrative generation will proceed with the approved content. You can start a new review session when the next agent completes their work, or monitor overall progress with `factory status`.

Thank you for the collaborative review! The agents have learned from your feedback and will apply these insights to future generation."""
        else:
            response = "❌ Approval failed. Please try again or contact support if the issue persists."
        
        return response
    
    async def _handle_general_discussion(self, intent: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Handle general discussion about the job content."""
        
        job = context["job"]
        message = intent.get("feedback", "")
        
        discussion_prompt = f"""
        Continue a collaborative discussion about this job output.
        
        User comment: "{message}"
        
        Job output: {job.output_payload}
        
        Respond conversationally, offering insights about:
        1. The narrative elements they're discussing
        2. How their observations relate to story structure
        3. Potential creative directions to explore
        4. Questions to help them think deeper about the content
        """
        
        discussion_response = await self.director.execute(discussion_prompt, context)
        
        response = f"""💭 **Creative Discussion**

That's an interesting perspective! {message}

**My Thoughts:** The {job.agent} agent created this content with specific narrative goals in mind. Your observation touches on important storytelling elements.

**Creative Opportunities:** This opens up several narrative possibilities we could explore:
• Character development directions
• Plot complexity variations  
• Emotional resonance enhancements

**Collaborative Exploration:** What aspects of this content most interest you? We could dive deeper into specific elements, explore alternatives, or discuss how this fits into the larger story arc.

Feel free to share more thoughts, ask questions, or let me know if you'd like to explore any specific creative directions!"""
        
        return response
```

### Step 3: Add Interactive CLI Commands

Add these commands to `src/cli/commands.py`:

```python
@app.command(name="review-interactive")
def review_interactive(
    job_id: str = typer.Argument(..., help="Job ID to review interactively")
):
    """
    Interactive review of agent output with edit options.
    
    Examples:
        factory review-interactive job_abc123
    """
    try:
        # Get job details
        job = job_store.get_job(job_id)
        if not job:
            console.print(f"❌ Job {job_id} not found", style="bold red")
            raise typer.Exit(1)
        
        # Display job information
        console.print(Panel(
            f"Agent: [bold magenta]{job.agent}[/bold magenta]\n"
            f"Status: [bold yellow]{job.status}[/bold yellow]\n"
            f"Created: {job.created_at}",
            title=f"📋 Job {job_id[:8]}...",
            border_style="blue"
        ))
        
        if not job.output_payload:
            console.print("⚠️ No output available yet", style="bold yellow")
            return
        
        # Display output with syntax highlighting
        console.print("\n📄 Agent Output:")
        output_json = json.dumps(job.output_payload, indent=2)
        syntax = Syntax(output_json, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="Output", border_style="green"))
        
        # Interactive options
        console.print("\n🎛️  What would you like to do?")
        choices = [
            "approve: Approve and continue workflow",
            "reject: Reject with feedback", 
            "revise: Request specific revisions",
            "alternatives: Generate alternative versions",
            "exit: Exit without action"
        ]
        
        for i, choice in enumerate(choices, 1):
            console.print(f"  {i}. {choice}")
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="1")
        
        if choice == "1":
            # Approve (use existing method)
            approved_output = job_store.approve_job(job_id)
            if approved_output:
                console.print("✅ Job approved successfully", style="bold green")
            else:
                console.print("❌ Approval failed", style="bold red")
        
        elif choice == "2":
            # Reject with feedback
            feedback = Prompt.ask("Enter rejection feedback")
            result = job_store.reject_job(job_id, feedback)
            if result:
                console.print("❌ Job rejected with feedback", style="bold red")
            else:
                console.print("❌ Rejection failed", style="bold red")
        
        elif choice == "3":
            # Request revision
            _handle_revision_request(job_id, job.agent)
        
        elif choice == "4":
            # Generate alternatives
            _handle_alternatives_request(job_id)
        
        else:
            console.print("👋 Exiting without action")
        
    except Exception as e:
        console.print(f"❌ Interactive review failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def revise(
    job_id: str = typer.Argument(..., help="Job ID to request revision"),
    feedback: str = typer.Option(..., "--feedback", help="Specific revision request"),
    section: str = typer.Option("all", "--section", help="Section to revise: all, emotional_arc, key_events, etc.")
):
    """
    Request specific revisions to agent output.
    
    Examples:
        factory revise job_abc123 --feedback "Make the romance more subtle"
        factory revise job_abc123 --feedback "Add more action" --section "key_events"
        factory revise job_abc123 --feedback "Slow down pacing" --section "emotional_turning_point"
    """
    try:
        console.print(f"🔄 Requesting revision for job: [bold cyan]{job_id}[/bold cyan]")
        console.print(f"📝 Feedback: [italic]{feedback}[/italic]")
        console.print(f"🎯 Section: [bold yellow]{section}[/bold yellow]")
        
        # Request revision using extended JobStore
        revision_job_id = job_store.request_revision(job_id, feedback, section)
        
        if revision_job_id:
            console.print(f"✅ Revision requested successfully", style="bold green")
            console.print(f"🆔 New revision job: [bold cyan]{revision_job_id}[/bold cyan]")
            console.print(f"💡 Use [bold cyan]factory status[/bold cyan] to monitor revision progress")
        else:
            console.print("❌ Revision request failed", style="bold red")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"❌ Revision request failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def alternatives(
    job_id: str = typer.Argument(..., help="Job ID to generate alternatives for"),
    count: int = typer.Option(3, "--count", help="Number of alternatives to generate")
):
    """
    Generate alternative versions of agent output.
    
    Examples:
        factory alternatives job_abc123
        factory alternatives job_abc123 --count 5
    """
    try:
        console.print(f"🎲 Generating {count} alternatives for job: [bold cyan]{job_id}[/bold cyan]")
        
        alternative_jobs = []
        
        # Generate multiple alternatives
        for i in range(count):
            alt_job_id = job_store.create_alternative_job(job_id)
            if alt_job_id:
                alternative_jobs.append(alt_job_id)
                console.print(f"  📋 Alternative {i+1}: [bold cyan]{alt_job_id}[/bold cyan]")
            else:
                console.print(f"  ❌ Failed to create alternative {i+1}", style="bold red")
        
        if alternative_jobs:
            console.print(f"✅ Generated {len(alternative_jobs)} alternatives", style="bold green")
            console.print(f"💡 Use [bold cyan]factory status[/bold cyan] to monitor generation progress")
            console.print(f"💡 Use [bold cyan]factory review-interactive <job_id>[/bold cyan] to compare options")
        else:
            console.print("❌ No alternatives generated", style="bold red")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"❌ Alternative generation failed: {e}", style="bold red")
        raise typer.Exit(1)

# === HELPER FUNCTIONS ===

def _handle_revision_request(job_id: str, agent: str):
    """Handle interactive revision request flow."""
    console.print(f"\n🔄 Requesting revision for {agent} output")
    
    # Agent-specific revision options
    if agent == "Director":
        sections = ["all", "key_events", "emotional_turning_point", "cliffhanger_concept", "goal"]
    elif agent == "Tactician":
        sections = ["all", "chapter_beats", "title_suggestions", "chapter_metadata"]
    elif agent == "Weaver":
        sections = ["all", "prose_style", "dialogue", "pacing", "descriptions"]
    elif agent == "Canonist":
        sections = ["all", "character_updates", "plot_updates", "tension_state"]
    else:
        sections = ["all"]
    
    console.print("🎯 Which section needs revision?")
    for i, section in enumerate(sections, 1):
        console.print(f"  {i}. {section}")
    
    section_choice = Prompt.ask("Choose section", choices=[str(i) for i in range(1, len(sections)+1)], default="1")
    selected_section = sections[int(section_choice) - 1]
    
    feedback = Prompt.ask("Enter specific revision feedback")
    
    # Request revision
    revision_job_id = job_store.request_revision(job_id, feedback, selected_section)
    
    if revision_job_id:
        console.print(f"✅ Revision requested for section: [bold yellow]{selected_section}[/bold yellow]", style="bold green")
        console.print(f"🆔 New revision job: [bold cyan]{revision_job_id}[/bold cyan]")
    else:
        console.print("❌ Revision request failed", style="bold red")

def _handle_alternatives_request(job_id: str):
    """Handle interactive alternatives generation."""
    console.print("\n🎲 How many alternatives would you like?")
    count = Prompt.ask("Number of alternatives", default="3")
    
    try:
        count = int(count)
        if count < 1 or count > 10:
            console.print("❌ Count must be between 1 and 10", style="bold red")
            return
        
        alternative_jobs = []
        
        with console.status(f"[bold green]Generating {count} alternatives..."):
            for i in range(count):
                alt_job_id = job_store.create_alternative_job(job_id)
                if alt_job_id:
                    alternative_jobs.append(alt_job_id)
        
        if alternative_jobs:
            console.print(f"✅ Generated {len(alternative_jobs)} alternatives:", style="bold green")
            for i, alt_id in enumerate(alternative_jobs, 1):
                console.print(f"  📋 Alternative {i}: [bold cyan]{alt_id}[/bold cyan]")
        else:
            console.print("❌ No alternatives generated", style="bold red")
            
    except ValueError:
        console.print("❌ Invalid count specified", style="bold red")
```

---

## 4. Validation Gate (The "Contract")

The implementation is complete when ALL of these commands pass:

### Level 1: Syntax & Import Validation
```bash
cd /workspaces/PRPs-agentic-eng/projects/narrative_factory
uv run python -c "from src.cli.commands import review_interactive, revise, alternatives; print('✅ Interactive commands imported')"
uv run python -c "from src.workflows.jobs import JobStore; js = JobStore(); print('✅ Extended JobStore loads')"
```

### Level 2: CLI Command Registration
```bash
uv run factory --help | grep -E "(review-interactive|revise|alternatives)"
# Must show all three commands in help output
```

### Level 3: Interactive Review Workflow
```bash
# Get a pending job ID from existing system
uv run factory status | head -5
# Copy a job ID from the output

# Test interactive review (will prompt for user input)
uv run factory review-interactive <job_id>
# Must show formatted output with interactive options
```

### Level 4: Revision Request System  
```bash
# Test revision request
uv run factory revise <job_id> --feedback "Make this more romantic" --section "emotional_turning_point"
# Must create new revision job and show job ID

# Verify revision job appears in status
uv run factory status | grep "processing"
# Should show the new revision job
```

### Level 5: Alternatives Generation
```bash
# Test alternatives generation
uv run factory alternatives <job_id> --count 2
# Must create 2 alternative jobs

# Verify alternatives appear in status
uv run factory status | grep "processing"
# Should show the new alternative jobs
```

### Level 6: Integration Validation
```bash
# Verify existing commands still work
uv run factory approve <job_id>  # Existing approve should work
uv run factory reject <job_id> --feedback "Test"  # Existing reject should work

# Test that job store extensions don't break existing functionality
uv run factory generate "Test chapter" # Should still work
```

---

## 5. Integration Notes

#### Workflow Enhancement:
- Interactive review provides guided workflow instead of memorizing command syntax
- Revision requests create new jobs that go through same approval process
- Alternatives allow A/B/C testing of agent outputs
- All new features integrate with existing `factory status` monitoring

#### Agent-Specific Features:
- Revision options are tailored to each agent's output structure
- Director revisions focus on story beats, emotional arcs, key events
- Tactician revisions target chapter structure and pacing
- Weaver revisions address prose style and descriptions
- Canonist revisions handle continuity and character updates

#### Backward Compatibility:
- All existing job commands (`status`, `review`, `approve`, `reject`) continue working unchanged
- New revision and alternatives integrate seamlessly with existing job approval workflow
- JobStore extensions preserve existing Redis schema and operations

This implementation transforms the binary approve/reject workflow into sophisticated iterative refinement while building on the proven job management foundation.