# In: src/narrative_factory/agents/models.py

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# MVP Simplified Models based on actual persona requirements

class StrategicBrief(BaseModel):
    """
    The official mission brief from the Director to the Tactician.
    Based on Director persona PROTOCOL 1: PROPULSION PROTOCOL output format.
    """
    # Header fields
    title: str = Field(description="A working title for the chapter/sequence")
    scope: Literal["SINGLE_CHAPTER", "MULTI_CHAPTER_ARC", "SAGA_GENESIS"] = Field(description="Strategic scope determination")
    estimated_chapters: str = Field(description="Director's estimate, e.g., '2-4' or '1'")
    pov_character_id: str = Field(description="Character name for POV")

    # Body fields
    goal: str = Field(description="Clear, one-sentence objective for the scene/sequence")
    key_events: List[str] = Field(description="Essential plot points framed as event descriptors")
    emotional_turning_point: str = Field(description="Core emotional shift directive")
    cliffhanger_concept: str = Field(description="One-sentence concept for chapter's final hook")

class ChapterBeatStructure(BaseModel):
    """
    Based on Tactician persona MANDATORY BEAT STRUCTURE from PROTOCOL 0.
    Each beat provides the Weaver with everything needed for compelling prose.
    """
    moment_anchor: str = Field(description="1-2 sentence present-tense physical action and sensory detail")
    internal_shift: str = Field(description="Character's from->to emotional/cognitive journey within this beat")
    micro_conflict: str = Field(description="Specific point of friction, resistance, or complication")
    narrative_payoff: Optional[str] = Field(None, description="System message, discovery, or key reveal for this beat")
    pacing_density: Literal["Expansive", "Moderate", "Compressed", "Crescendo", "Decrescendo"] = Field(
        default="Moderate", description="Pacing directive from Tactician appendix"
    )

class ChapterMetadata(BaseModel):
    """
    Based on Tactician persona step 7: Generate Chapter Metadata.
    """
    chapter_goal: str = Field(description="Core narrative objective in single sentence")
    hook_concept: str = Field(description="Core concept of final HOOK beat in single sentence")
    discovery_log: List[str] = Field(description="Key conceptual revelations protagonist makes")

class ChapterBlueprint(BaseModel):
    """
    The detailed, beat-by-beat blueprint from the Tactician to the Weaver.
    Based on Tactician persona PROTOCOL 0 final output structure.
    """
    # Section 1: Metadata
    metadata: ChapterMetadata = Field(description="Chapter goal, hook, and discovery log")

    # Section 2: Title suggestions
    title_suggestions: List[str] = Field(description="3-5 potential chapter titles from ChapterTitlingModule")

    # Section 3: Beat list
    beats: List[ChapterBeatStructure] = Field(description="3-7 granular scene beats as choreographic instructions")

    # Traceability
    brief_id: str = Field(description="ID of source StrategicBrief for traceability")

# Job State Models for Redis-based HITL workflow
class JobState(BaseModel):
    """
    Job state contract for Redis-based Human-in-the-Loop workflow.
    """
    job_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique job identifier")
    agent: Literal["Director", "Tactician", "Weaver", "Canonist"] = Field(description="Agent responsible")
    status: Literal["processing", "pending_approval", "approved", "rejected", "complete"] = Field(description="Current job status")
    input_payload: Dict = Field(description="Input data for the job")
    output_payload: Optional[Dict] = Field(None, description="Agent output data")
    feedback_history: List[Dict] = Field(default_factory=list, description="Human feedback iterations")
    created_at: datetime = Field(default_factory=datetime.now, description="Job creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

# Memory/Context Models for MVP simplified two-tiered retrieval
class MemoryDocument(BaseModel):
    """
    Simplified document model for MVP Qdrant storage.
    """
    id: str = Field(description="Document identifier")
    content: str = Field(description="Document text content")
    doc_type: Literal["character_sheet", "style_guide", "lore_document", "tension_report"] = Field(description="Document classification")
    present_characters: List[str] = Field(default_factory=list, description="Character IDs for spotlight filtering")
    metadata: Dict = Field(default_factory=dict, description="Additional document metadata")

class ContextRetrievalResult(BaseModel):
    """
    Two-tiered context retrieval result from memory pipeline.
    """
    spotlight_context: List[Dict] = Field(description="High-relevance context for current POV/scene")
    ambient_echo: List[Dict] = Field(description="Background tension and unresolved conflicts")
