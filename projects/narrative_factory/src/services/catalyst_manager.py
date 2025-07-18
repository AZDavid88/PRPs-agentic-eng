"""
Catalyst Manager for creative injection into narrative generation workflows.

Provides persistent storage and management of creative catalysts that can be
injected into story generation to influence direction and creativity.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.config import STATE_DIR
from src.logger import get_logger
from src.workflows.jobs import JobStore

logger = get_logger(__name__)


class Catalyst(BaseModel):
    """A creative catalyst for story generation influence."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str = Field(..., description="The creative catalyst description")
    target: str = Field(default="next", description="Target story or 'next' for next generation")
    priority: int = Field(default=5, ge=1, le=10, description="Priority level 1-10")
    created_at: datetime = Field(default_factory=datetime.now)
    used_at: Optional[datetime] = Field(default=None, description="When this catalyst was used")
    status: str = Field(default="active", description="Status: active, used, expired")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CatalystManager:
    """Enhanced catalyst management integrated with existing workflow patterns."""

    def __init__(self, state_dir: Path = STATE_DIR, job_store: Optional[JobStore] = None):
        self.state_dir = state_dir
        self.catalyst_file = self.state_dir / "catalysts.json"
        self.job_store = job_store or JobStore()

    async def add_catalyst(
        self,
        description: str,
        target: str = "next",
        priority: int = 5,
        metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Add a new catalyst to the system."""
        catalyst = Catalyst(
            description=description,
            target=target,
            priority=priority,
            metadata=metadata or {}
        )

        try:
            # Load existing catalysts
            catalysts = await self._load_catalysts()
            catalysts[catalyst.id] = catalyst

            # Save updated catalysts
            await self._save_catalysts(catalysts)

            # Store metadata in job store for workflow integration
            if self.job_store:
                await asyncio.to_thread(
                    self.job_store.redis_client.set,
                    f"catalyst_{catalyst.id}",
                    json.dumps({
                        "description": catalyst.description,
                        "target": catalyst.target,
                        "priority": catalyst.priority,
                        "created_at": catalyst.created_at.isoformat(),
                        "status": catalyst.status
                    })
                )

            logger.info(f"Added catalyst {catalyst.id[:8]} with priority {priority}")
            return catalyst.id

        except Exception as e:
            logger.error(f"Failed to add catalyst: {e}")
            raise

    async def get_catalysts_for_target(self, target: str = "next") -> list[Catalyst]:
        """Get active catalysts for a specific target, sorted by priority."""
        try:
            catalysts = await self._load_catalysts()

            # Filter active catalysts for target
            active_catalysts = [
                catalyst for catalyst in catalysts.values()
                if catalyst.status == "active" and catalyst.target == target
            ]

            # Sort by priority (highest first)
            return sorted(active_catalysts, key=lambda c: c.priority, reverse=True)

        except Exception as e:
            logger.error(f"Failed to get catalysts for target {target}: {e}")
            return []

    async def use_catalyst(self, catalyst_id: str) -> bool:
        """Mark a catalyst as used."""
        try:
            catalysts = await self._load_catalysts()

            if catalyst_id in catalysts:
                catalysts[catalyst_id].status = "used"
                catalysts[catalyst_id].used_at = datetime.now()

                await self._save_catalysts(catalysts)

                # Update job store metadata
                if self.job_store:
                    await asyncio.to_thread(
                        self.job_store.redis_client.set,
                        f"catalyst_{catalyst_id}",
                        json.dumps({
                            "status": "used",
                            "used_at": catalysts[catalyst_id].used_at.isoformat()
                        })
                    )

                logger.info(f"Marked catalyst {catalyst_id[:8]} as used")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to mark catalyst as used: {e}")
            return False

    async def get_catalyst_summary(self) -> dict[str, Any]:
        """Get a summary of all catalysts in the system."""
        try:
            catalysts = await self._load_catalysts()

            summary = {
                "total_catalysts": len(catalysts),
                "active_catalysts": len([c for c in catalysts.values() if c.status == "active"]),
                "used_catalysts": len([c for c in catalysts.values() if c.status == "used"]),
                "recent_catalysts": []
            }

            # Get recent catalysts (last 5)
            recent = sorted(
                catalysts.values(),
                key=lambda c: c.created_at,
                reverse=True
            )[:5]

            for catalyst in recent:
                summary["recent_catalysts"].append({
                    "id": catalyst.id[:8],
                    "description": catalyst.description,
                    "priority": catalyst.priority,
                    "status": catalyst.status,
                    "target": catalyst.target
                })

            return summary

        except Exception as e:
            logger.error(f"Failed to get catalyst summary: {e}")
            return {"error": str(e)}

    async def _load_catalysts(self) -> dict[str, Catalyst]:
        """Load catalysts from storage."""
        try:
            if self.catalyst_file.exists():
                content = await asyncio.to_thread(self.catalyst_file.read_text, encoding='utf-8')
                data = json.loads(content)

                # Convert back to Catalyst objects
                catalysts = {}
                for catalyst_id, catalyst_data in data.items():
                    catalysts[catalyst_id] = Catalyst(**catalyst_data)

                return catalysts

            return {}

        except Exception as e:
            logger.error(f"Failed to load catalysts: {e}")
            return {}

    async def _save_catalysts(self, catalysts: dict[str, Catalyst]) -> None:
        """Save catalysts to storage."""
        try:
            # Convert to serializable format
            data = {}
            for catalyst_id, catalyst in catalysts.items():
                data[catalyst_id] = catalyst.model_dump()

            content = json.dumps(data, indent=2, default=str)
            await asyncio.to_thread(self.catalyst_file.write_text, content, encoding='utf-8')

        except Exception as e:
            logger.error(f"Failed to save catalysts: {e}")
            raise
