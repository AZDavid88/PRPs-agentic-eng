"""
Agent personas implementation for the Narrative Factory.
Provides base Agent class and specific agent subclasses (Director, Tactician, Weaver, Canonist).
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

try:
    from google import genai  # type: ignore
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .models import ChapterBlueprint, StrategicBrief


class Agent(ABC):
    """
    Base class for all narrative agents.
    Handles common initialization, persona loading, and LLM client setup.
    """

    def __init__(self, persona_name: str, client_type: str = "gemini"):
        """
        Initialize the agent with a persona name and client type.
        
        Args:
            persona_name: Name of the persona (director, tactician, weaver, canonist)
            client_type: Either "gemini" or "openai"
        """
        self.persona_name = persona_name
        self.client_type = client_type
        self.persona_content: Optional[str] = None
        self.client: Any = None

        self._load_persona()
        self._initialize_client()

    def _load_persona(self) -> None:
        """Load persona content from the prompts directory."""
        try:
            # Get the path to the prompts directory
            current_dir = Path(__file__).parent
            prompts_dir = current_dir / "prompts"
            persona_file = prompts_dir / f"{self.persona_name}.txt"

            if persona_file.exists():
                with open(persona_file, encoding='utf-8') as f:
                    self.persona_content = f.read()
            else:
                raise FileNotFoundError(f"Persona file not found: {persona_file}")

        except Exception as e:
            raise RuntimeError(f"Failed to load persona {self.persona_name}: {e}")

    def _initialize_client(self) -> None:
        """Initialize the appropriate LLM client based on client_type."""
        try:
            if self.client_type == "gemini":
                if not GENAI_AVAILABLE:
                    raise ImportError("google.genai not available")

                # Modern Google GenAI SDK uses environment variables automatically
                # or can be configured with api_key parameter
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if api_key:
                    self.client = genai.Client(api_key=api_key)
                else:
                    # Try using environment variables automatically
                    self.client = genai.Client()

            elif self.client_type == "openai":
                if not OPENAI_AVAILABLE:
                    raise ImportError("openai not available")

                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable required")

                self.client = OpenAI(api_key=api_key)

            else:
                raise ValueError(f"Unsupported client_type: {self.client_type}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize {self.client_type} client: {e}")

    def _generate_content(self, prompt: str) -> str:
        """
        Generate content using the configured LLM client.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated text response
        """
        try:
            if self.client_type == "gemini" and self.client:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                return str(response.text)

            elif self.client_type == "openai" and self.client:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": self.persona_content or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content or ""
            else:
                raise RuntimeError(f"Client not initialized for {self.client_type}")

        except Exception as e:
            raise RuntimeError(f"Failed to generate content: {e}")

    def _generate_structured_content(self, prompt: str, response_model: Type[T]) -> T:
        """
        Generate structured content using Pydantic models for validation.
        Uses modern SDK features for automatic validation.
        
        Args:
            prompt: The prompt to send to the LLM
            response_model: Pydantic model class for response validation
            
        Returns:
            Validated Pydantic model instance
        """
        try:
            if self.client_type == "gemini" and self.client:
                # Use structured output with Pydantic model
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': response_model,
                    }
                )
                # Parse and validate with Pydantic
                return response_model.model_validate_json(response.text)

            elif self.client_type == "openai" and self.client:
                # Use OpenAI's structured output with parse method
                response = self.client.chat.completions.parse(
                    model="gpt-4o-2024-08-06",
                    messages=[
                        {"role": "system", "content": self.persona_content or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=response_model,
                    temperature=0.7,
                    max_tokens=2000
                )

                if response.choices[0].message.parsed:
                    return response.choices[0].message.parsed  # type: ignore
                else:
                    raise RuntimeError("Failed to parse structured response")
            else:
                raise RuntimeError(f"Client not initialized for {self.client_type}")

        except Exception as e:
            # Fallback to text generation and manual parsing
            response_text = self._generate_content(prompt)
            try:
                # Try to extract JSON from response
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                elif "{" in response_text and "}" in response_text:
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    json_str = response_text[start:end]
                else:
                    json_str = response_text

                import json
                response_dict = json.loads(json_str)
                return response_model.model_validate(response_dict)
            except Exception:
                raise RuntimeError(f"Failed to generate structured content: {e}")

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the agent's primary function.
        Must be implemented by subclasses.
        """
        pass


class DirectorAgent(Agent):
    """
    The Director agent responsible for strategic narrative planning.
    Returns StrategicBrief Pydantic models.
    """

    def __init__(self, client_type: str = "gemini"):
        super().__init__("director", client_type)

    def execute(self, chapter_seed: str, context: Optional[Dict[str, Any]] = None) -> StrategicBrief:
        """
        Execute the Director's strategic planning protocol.
        
        Args:
            chapter_seed: Initial narrative seed or continuation point
            context: Optional context dictionary with additional information
            
        Returns:
            StrategicBrief: Validated Pydantic model with strategic direction
        """
        try:
            # Construct the full prompt with persona context
            full_prompt = f"""
{self.persona_content}

Current narrative context: {context or {}}

Chapter seed: {chapter_seed}

Please analyze this narrative state and provide a strategic brief with the following structure:
- Title: A working title for the chapter/sequence
- Scope: Determine if this is SINGLE_CHAPTER, MULTI_CHAPTER_ARC, or SAGA_GENESIS
- Estimated chapters: Your estimate (e.g., '2-4' or '1')
- POV character: Character name for the POV
- Goal: Clear, one-sentence objective for the scene/sequence
- Key events: Essential plot points as event descriptors
- Emotional turning point: Core emotional shift directive
- Cliffhanger concept: One-sentence concept for chapter's final hook

Respond with a JSON object that matches this structure exactly.
"""

            # Use structured content generation with automatic Pydantic validation
            try:
                return self._generate_structured_content(full_prompt, StrategicBrief)
            except Exception:
                # Fallback: create a basic StrategicBrief from the text response
                return StrategicBrief(
                    title=f"Chapter: {chapter_seed[:50]}...",
                    scope="SINGLE_CHAPTER",
                    estimated_chapters="1",
                    pov_character_id="protagonist",
                    goal=f"Advance the narrative from: {chapter_seed}",
                    key_events=[chapter_seed],
                    emotional_turning_point="Character faces a new challenge",
                    cliffhanger_concept="Tension escalates for next chapter"
                )

        except Exception as e:
            raise RuntimeError(f"DirectorAgent execution failed: {e}") from e


class TacticianAgent(Agent):
    """
    The Tactician agent responsible for tactical chapter planning.
    Accepts StrategicBrief and returns ChapterBlueprint.
    """

    def __init__(self, client_type: str = "gemini"):
        super().__init__("tactician", client_type)

    def execute(self, strategic_brief: StrategicBrief, context: Optional[Dict[str, Any]] = None) -> ChapterBlueprint:
        """
        Execute the Tactician's tactical planning protocol.
        
        Args:
            strategic_brief: StrategicBrief from Director
            context: Optional context dictionary
            
        Returns:
            ChapterBlueprint: Validated Pydantic model with tactical chapter plan
        """
        try:
            # Construct prompt with strategic brief context
            full_prompt = f"""
{self.persona_content}

Strategic Brief from Director:
- Title: {strategic_brief.title}
- Scope: {strategic_brief.scope}
- Estimated chapters: {strategic_brief.estimated_chapters}
- POV Character: {strategic_brief.pov_character_id}
- Goal: {strategic_brief.goal}
- Key Events: {strategic_brief.key_events}
- Emotional Turning Point: {strategic_brief.emotional_turning_point}
- Cliffhanger: {strategic_brief.cliffhanger_concept}

Additional context: {context or {}}

Create a detailed chapter blueprint with:
1. Metadata (chapter_goal, hook_concept, discovery_log)
2. Title suggestions (3-5 options)
3. Beats (3-7 scene beats with moment_anchor, internal_shift, micro_conflict, narrative_payoff, pacing_density)

Respond with a JSON object matching the ChapterBlueprint structure.
"""

            # Use structured content generation with automatic Pydantic validation
            try:
                return self._generate_structured_content(full_prompt, ChapterBlueprint)
            except Exception:
                # Fallback: create a basic ChapterBlueprint
                from .models import ChapterBeatStructure, ChapterMetadata

                return ChapterBlueprint(
                    metadata=ChapterMetadata(
                        chapter_goal=strategic_brief.goal,
                        hook_concept=strategic_brief.cliffhanger_concept,
                        discovery_log=["Key revelation from strategic brief"]
                    ),
                    title_suggestions=[strategic_brief.title, f"Alternative: {strategic_brief.title}"],
                    beats=[
                        ChapterBeatStructure(
                            moment_anchor="Scene opens with character in action",
                            internal_shift="Character moves from uncertainty to determination",
                            micro_conflict="Obstacle or resistance appears",
                            narrative_payoff="Important information or realization",
                            pacing_density="Moderate"
                        )
                    ],
                    brief_id=f"brief_{strategic_brief.title.lower().replace(' ', '_')}"
                )

        except Exception as e:
            raise RuntimeError(f"TacticianAgent execution failed: {e}") from e


class WeaverAgent(Agent):
    """
    The Weaver agent responsible for prose generation.
    Placeholder implementation for now.
    """

    def __init__(self, client_type: str = "gemini"):
        super().__init__("weaver", client_type)

    def execute(self, chapter_blueprint: ChapterBlueprint, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute the Weaver's prose generation protocol.
        
        Args:
            chapter_blueprint: ChapterBlueprint from Tactician
            context: Optional context dictionary
            
        Returns:
            str: Generated prose chapter (placeholder implementation)
        """
        # Placeholder implementation
        return f"Generated prose for chapter: {chapter_blueprint.metadata.chapter_goal}"


class CanonistAgent(Agent):
    """
    The Canonist agent responsible for continuity and canon management.
    Placeholder implementation for now.
    """

    def __init__(self, client_type: str = "gemini"):
        super().__init__("canonist", client_type)

    def execute(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the Canonist's continuity validation protocol.
        
        Args:
            content: Content to validate against canon
            context: Optional context dictionary
            
        Returns:
            Dict[str, Any]: Validation results (placeholder implementation)
        """
        # Placeholder implementation
        return {
            "validation_status": "passed",
            "notes": "Continuity check completed",
            "suggestions": []
        }
