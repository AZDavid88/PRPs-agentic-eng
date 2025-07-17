"""Upstash Redis-based JobStore for stateful HITL workflows."""

from datetime import datetime
from typing import Literal, Optional

from dotenv import load_dotenv
from upstash_redis import Redis

from src.models import JobState

# Load environment variables from .env file
load_dotenv()


class JobStore:
    """Upstash Redis-based job store for managing stateful HITL workflow jobs."""

    def __init__(self) -> None:
        """Initialize Upstash Redis client from environment variables."""
        self.redis_client = Redis.from_env()

    def create_job(self, agent: Literal["Director", "Tactician", "Weaver", "Canonist"], input_payload: dict) -> str:
        """Create new job in Redis and return job_id.

        Args:
            agent: Name of the agent (Director, Tactician, etc.)
            input_payload: Input data for the agent

        Returns:
            str: Generated job ID
        """
        job = JobState(
            agent=agent,
            status="processing",
            input_payload=input_payload,
            output_payload=None
        )
        self.redis_client.set(f"job:{job.job_id}", job.model_dump_json())
        return job.job_id

    def update_job_as_pending(self, job_id: str, output_payload: dict) -> None:
        """Update job with output and set status to pending_approval.

        Args:
            job_id: Job identifier
            output_payload: Output data from agent execution
        """
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            job = JobState.model_validate_json(job_data)
            job.status = "pending_approval"
            job.output_payload = output_payload
            job.updated_at = datetime.now()
            self.redis_client.set(f"job:{job_id}", job.model_dump_json())

    def approve_job(self, job_id: str) -> Optional[dict]:
        """Approve job and return output payload.

        Args:
            job_id: Job identifier

        Returns:
            Optional[dict]: Output payload if job exists, None otherwise
        """
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            job = JobState.model_validate_json(job_data)
            job.status = "approved"
            job.updated_at = datetime.now()
            self.redis_client.set(f"job:{job_id}", job.model_dump_json())
            return job.output_payload
        return None

    def reject_job(self, job_id: str, feedback: str = "") -> Optional[dict]:
        """Reject job and return input payload for retry.

        Args:
            job_id: Job identifier
            feedback: Human feedback for improvement

        Returns:
            Optional[dict]: Input payload if job exists, None otherwise
        """
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            job = JobState.model_validate_json(job_data)
            job.status = "rejected"
            job.feedback_history.append({
                "timestamp": datetime.now().isoformat(),
                "feedback": feedback
            })
            job.updated_at = datetime.now()
            self.redis_client.set(f"job:{job_id}", job.model_dump_json())
            return job.input_payload
        return None

    def get_job(self, job_id: str) -> Optional[JobState]:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Optional[JobState]: Job state if exists, None otherwise
        """
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            return JobState.model_validate_json(job_data)
        return None

    def get_pending_jobs(self) -> list[JobState]:
        """Get all jobs with pending_approval status.

        Returns:
            List[JobState]: List of jobs awaiting approval
        """
        jobs = []
        # Upstash Redis doesn't support scan_iter, use keys instead
        # In production, consider maintaining a separate index
        keys = self.redis_client.keys("job:*")
        for key in keys:
            job_data = self.redis_client.get(key)
            if job_data:
                job = JobState.model_validate_json(job_data)
                if job.status == "pending_approval":
                    jobs.append(job)
        return jobs

    def get_jobs_by_status(self, status: str) -> list[JobState]:
        """Get all jobs with specific status.

        Args:
            status: Job status to filter by

        Returns:
            List[JobState]: List of jobs with matching status
        """
        jobs = []
        # Upstash Redis doesn't support scan_iter, use keys instead
        # In production, consider maintaining a separate index
        keys = self.redis_client.keys("job:*")
        for key in keys:
            job_data = self.redis_client.get(key)
            if job_data:
                job = JobState.model_validate_json(job_data)
                if job.status == status:
                    jobs.append(job)
        return jobs

    def delete_job(self, job_id: str) -> bool:
        """Delete job from Redis.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if job was deleted, False if not found
        """
        return bool(self.redis_client.delete(f"job:{job_id}"))

    def health_check(self) -> bool:
        """Check Upstash Redis connection health.

        Returns:
            bool: True if Redis is accessible, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
