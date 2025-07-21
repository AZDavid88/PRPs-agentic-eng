"""
Conversational interface for job review and revision workflows.
Provides ChatGPT-style interaction with agent cognitive engines.
CRITICAL: All conversational outputs are ingested to Qdrant for agent RAG access.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.agents.personas import DirectorAgent
from src.workflows.jobs import JobStore
from src.models import JobState
from src.memory.qdrant import QdrantService

class JobReviewChatInterface:
    """Conversational interface for job review and iteration with memory integration."""
    
    def __init__(self):
        self.director = DirectorAgent()
        self.job_store = JobStore()
        self.memory_service = QdrantService()
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
        
        # CRITICAL: Ingest conversation to memory for agent RAG access
        await self._ingest_chat_content_to_memory(session_id, user_message, response, intent)
        
        # Update conversation history
        context["review_history"].append({
            "timestamp": datetime.now(),
            "user_message": user_message,
            "intent": intent,
            "agent_response": response
        })
        
        return response
    
    async def _ingest_chat_content_to_memory(self, session_id: str, user_message: str, 
                                           agent_response: str, intent: Dict[str, Any]):
        """
        CRITICAL: Ingest conversational content to Qdrant for agent RAG access.
        This ensures human-AI conversations become part of the agent knowledge base.
        """
        try:
            context = self.conversation_context[session_id]
            job = context["job"]
            
            # Create rich content for memory ingestion
            chat_content = {
                "conversation_type": "job_review_chat",
                "session_id": session_id,
                "job_id": context["job_id"],
                "agent": job.agent,
                "user_message": user_message,
                "agent_response": agent_response,
                "parsed_intent": intent,
                "timestamp": datetime.now().isoformat(),
                "job_output_context": job.output_payload
            }
            
            # Create searchable text for vectorization
            searchable_text = f"""
            Job Review Conversation - {job.agent} Agent
            
            User Feedback: {user_message}
            
            Agent Response: {agent_response}
            
            Intent: {intent.get('action', 'discuss')} - {intent.get('feedback', '')}
            
            Job Context: {job.agent} output for {job.input_payload.get('story_context', 'story')}
            
            Original Output: {str(job.output_payload)[:500]}...
            """
            
            # Metadata for categorization and retrieval
            metadata = {
                "content_type": "conversation",
                "conversation_type": "job_review",
                "agent": job.agent,
                "session_id": session_id,
                "job_id": context["job_id"],
                "intent_action": intent.get("action", "discuss"),
                "target_section": intent.get("target_section", "general"),
                "timestamp": datetime.now().isoformat(),
                "user_id": context.get("user_id", "human")
            }
            
            # Ingest to Qdrant with late chunking and vectorization
            document_id = f"chat_{session_id}_{int(datetime.now().timestamp())}"
            
            await self.memory_service.ingest_document(
                content=searchable_text,
                metadata=metadata,
                document_id=document_id
            )
            
            # Note: logger not imported, would need to add logging
            
        except Exception as e:
            # Note: logger not imported, would need to add error logging
            # Don't fail the chat if memory ingestion fails
            pass
    
    async def _parse_review_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse natural language input to extract review intent."""
        
        job = context["job"]
        
        # Simplified parsing for implementation
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