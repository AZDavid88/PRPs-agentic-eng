"""Prefect flows for narrative generation with HITL checkpoints."""

from typing import Optional

from prefect import flow, get_run_logger, task
from prefect.tasks import exponential_backoff

from src.agents.personas import CanonistAgent, DirectorAgent, TacticianAgent, WeaverAgent
from src.memory.qdrant import QdrantService
from src.services.state_manager import StateManager
from src.workflows.jobs import JobStore

# Initialize services
job_store = JobStore()
memory_service = QdrantService()
state_manager = StateManager()


@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def director_task(chapter_seed: str, active_characters: Optional[list[str]] = None, catalyst: Optional[str] = None, dry_run: bool = False) -> str:
    """Execute Director agent and save result to JobStore for HITL review.

    Args:
        chapter_seed: Initial narrative seed
        active_characters: List of character IDs to include
        catalyst: Optional creative catalyst to inject
        dry_run: If True, skip actual LLM calls and return mock results

    Returns:
        str: Job ID for the pending Director task
    """
    logger = get_run_logger()

    if active_characters is None:
        active_characters = ["char_protagonist"]

    logger.info(f"Starting Director task with seed: {chapter_seed}")

    # Create job in JobStore
    job_id = job_store.create_job(
        agent="Director",
        input_payload={
            "chapter_seed": chapter_seed,
            "active_characters": active_characters,
            "catalyst": catalyst,
            "dry_run": dry_run
        }
    )

    try:
        if dry_run:
            # Dry run mode - return mock results without LLM calls
            logger.info("DRY RUN MODE: Skipping actual Director agent execution")
            mock_strategic_brief = {
                "strategic_brief": f"Mock strategic brief for seed: {chapter_seed}",
                "catalyst_applied": catalyst if catalyst else "None",
                "dry_run": True,
                "mock_data": True
            }
            job_store.update_job_as_pending(job_id, mock_strategic_brief)
            logger.info(f"Dry run Director task complete. Job ID: {job_id}")
            return job_id

        # Get context from memory service
        context = await memory_service.fetch_context_for_director(chapter_seed, active_characters)

        # Enhance context with catalyst if provided
        if catalyst:
            logger.info(f"Applying catalyst: {catalyst}")
            context_dict = context.model_dump()
            context_dict["catalyst"] = catalyst
            context = context.model_validate(context_dict)

        # Execute Director agent
        director = DirectorAgent()
        strategic_brief = director.execute(chapter_seed, context.model_dump())

        # Save output and mark as pending approval
        job_store.update_job_as_pending(job_id, strategic_brief.model_dump())

        logger.info(f"Director task complete. Job ID: {job_id}")
        return job_id

    except Exception as e:
        logger.error(f"Director task failed: {str(e)}")
        # Update job with error status
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "status": "failed"
        })
        raise


@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def tactician_task(director_job_id: str) -> str:
    """Execute Tactician agent using approved Director output.

    Args:
        director_job_id: Job ID of the approved Director task

    Returns:
        str: Job ID for the pending Tactician task
    """
    logger = get_run_logger()

    # Get approved Director output
    director_output = job_store.approve_job(director_job_id)
    if not director_output:
        raise ValueError(f"Director job {director_job_id} not approved or not found")

    logger.info(f"Starting Tactician task with approved Director job: {director_job_id}")

    # Create new job for Tactician
    job_id = job_store.create_job(
        agent="Tactician",
        input_payload={"strategic_brief": director_output}
    )

    try:
        # Import and reconstruct the StrategicBrief from dict
        from src.models import StrategicBrief
        strategic_brief = StrategicBrief.model_validate(director_output)

        # Execute Tactician agent
        tactician = TacticianAgent()
        chapter_blueprint = tactician.execute(strategic_brief)

        # Save output and mark as pending approval
        job_store.update_job_as_pending(job_id, chapter_blueprint.model_dump())

        logger.info(f"Tactician task complete. Job ID: {job_id}")
        return job_id

    except Exception as e:
        logger.error(f"Tactician task failed: {str(e)}")
        # Update job with error status
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "status": "failed"
        })
        raise


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def weaver_task(tactician_job_id: str) -> str:
    """Execute Weaver agent (automated, no approval needed).

    Args:
        tactician_job_id: Job ID of the approved Tactician task

    Returns:
        str: Generated chapter text
    """
    logger = get_run_logger()

    # Get approved Tactician output
    tactician_output = job_store.approve_job(tactician_job_id)
    if not tactician_output:
        raise ValueError(f"Tactician job {tactician_job_id} not approved or not found")

    logger.info(f"Starting Weaver task with approved Tactician job: {tactician_job_id}")

    try:
        # Import and reconstruct the ChapterBlueprint from dict
        from src.models import ChapterBlueprint
        chapter_blueprint = ChapterBlueprint.model_validate(tactician_output)

        # Execute Weaver agent
        weaver = WeaverAgent()
        chapter_text = weaver.execute(chapter_blueprint)

        # Save final output (no approval needed for Weaver)
        job_id = job_store.create_job(
            agent="Weaver",
            input_payload={"chapter_blueprint": tactician_output}
        )
        job_store.update_job_as_pending(job_id, {"chapter_text": chapter_text})

        logger.info(f"Weaver task complete. Generated {len(chapter_text.split())} words")
        return chapter_text

    except Exception as e:
        logger.error(f"Weaver task failed: {str(e)}")
        raise


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def canonist_task(chapter_text: str, chapter_blueprint: dict, story_id: Optional[str] = None) -> dict:
    """Execute Canonist agent for final validation and state management (automated).

    Args:
        chapter_text: Generated chapter text from Weaver
        chapter_blueprint: Chapter blueprint from Tactician
        story_id: Optional story ID for state management

    Returns:
        dict: Canonist analysis results and updated story state
    """
    logger = get_run_logger()

    logger.info("Starting Canonist validation and state management task")

    try:
        # Load current story state
        current_state = await state_manager.load_latest_state(story_id)
        logger.info(f"Loaded story state for chapter {current_state.current_chapter}")

        # Execute Canonist agent
        canonist = CanonistAgent()
        canonist_results = await canonist.execute(chapter_text, chapter_blueprint)

        # Generate updated story state from canonist output
        updated_state = state_manager.create_state_from_canonist_output(canonist_results, current_state)

        # Save updated state
        save_success = await state_manager.save_state(updated_state, story_id)
        if not save_success:
            logger.warning("Failed to save updated story state")

        logger.info(f"Canonist validation complete. New state saved for chapter {updated_state.current_chapter}")

        # Return both validation results and state info
        return {
            "validated_text": chapter_text,
            "canonist_analysis": canonist_results,
            "story_state": updated_state.model_dump(),
            "state_saved": save_success
        }

    except Exception as e:
        logger.error(f"Canonist task failed: {str(e)}")
        raise


@flow(name="Initial Generation Flow", log_prints=True)
async def initial_generation_flow(chapter_seed: str, active_characters: Optional[list[str]] = None, catalyst: Optional[str] = None, dry_run: bool = False) -> str:
    """Initial flow: Director task only, then pause for HITL approval.

    Args:
        chapter_seed: Initial narrative seed
        active_characters: List of character IDs to include
        catalyst: Optional creative catalyst to inject
        dry_run: If True, perform dry run without LLM calls

    Returns:
        str: Director job ID awaiting approval
    """
    logger = get_run_logger()

    logger.info(f"Starting narrative generation with seed: {chapter_seed}")

    # Execute Director task with enhanced parameters
    director_job_id = await director_task(chapter_seed, active_characters, catalyst, dry_run)

    if dry_run:
        logger.info(f"DRY RUN Director task complete. Job ID: {director_job_id}")
        logger.info("DRY RUN MODE - No actual LLM execution performed")
    else:
        logger.info(f"Director task complete. Job ID: {director_job_id}")
        logger.info("HUMAN REVIEW REQUIRED")
        logger.info(f"Use CLI to review and approve: factory.py review {director_job_id}")

    return director_job_id


@flow(name="Continue Generation Flow", log_prints=True)
def continue_generation_flow(director_job_id: str) -> str:
    """Continue flow: Tactician task after Director approval, then pause for approval.

    Args:
        director_job_id: Approved Director job ID

    Returns:
        str: Tactician job ID awaiting approval
    """
    logger = get_run_logger()

    logger.info(f"Continuing generation with approved Director job: {director_job_id}")

    # Execute Tactician task
    tactician_job_id = tactician_task(director_job_id)

    logger.info(f"Tactician task complete. Job ID: {tactician_job_id}")
    logger.info("HUMAN REVIEW REQUIRED")
    logger.info(f"Use CLI to review and approve: factory.py review {tactician_job_id}")

    return tactician_job_id


@flow(name="Finalize Generation Flow", log_prints=True)
async def finalize_generation_flow(tactician_job_id: str, story_id: Optional[str] = None) -> dict:
    """Final flow: Weaver and Canonist tasks (automated).

    Args:
        tactician_job_id: Approved Tactician job ID
        story_id: Optional story ID for state management

    Returns:
        dict: Final chapter results with story state
    """
    logger = get_run_logger()

    logger.info(f"Finalizing generation with approved Tactician job: {tactician_job_id}")

    # Get tactician output for Canonist
    tactician_output = job_store.get_job(tactician_job_id)
    if not tactician_output or tactician_output.status != "approved":
        raise ValueError(f"Tactician job {tactician_job_id} not approved")

    # Execute Weaver task
    chapter_text = weaver_task(tactician_job_id)

    # Execute Canonist task for final validation and state management
    canonist_results = await canonist_task(chapter_text, tactician_output.output_payload, story_id)

    logger.info("Chapter generation complete!")
    logger.info(f"Final chapter: {len(str(canonist_results['validated_text']).split())} words")
    logger.info(f"Story state updated: Chapter {canonist_results['story_state']['current_chapter']}")

    return canonist_results


@flow(name="Full Generation Flow", log_prints=True)
async def full_generation_flow(
    chapter_seed: str,
    active_characters: Optional[list[str]] = None,
    auto_approve: bool = False,
    story_id: Optional[str] = None
) -> dict:
    """Complete generation flow with optional auto-approval for testing.

    Args:
        chapter_seed: Initial narrative seed
        active_characters: List of character IDs to include
        auto_approve: If True, automatically approve all stages (testing only)
        story_id: Optional story ID for state management

    Returns:
        dict: Final chapter results with story state
    """
    logger = get_run_logger()

    if auto_approve:
        logger.warning("AUTO-APPROVAL ENABLED - FOR TESTING ONLY")

    logger.info(f"Starting full generation flow with seed: {chapter_seed}")

    # Load current story state for context
    current_state = await state_manager.load_latest_state(story_id)
    logger.info(f"Loaded story state for chapter {current_state.current_chapter}")

    # Step 1: Director
    director_job_id = await director_task(chapter_seed, active_characters)

    if auto_approve:
        job_store.approve_job(director_job_id)
        logger.info(f"Auto-approved Director job: {director_job_id}")
    else:
        logger.info(f"Director job {director_job_id} requires manual approval")
        return {"status": "pending_director_approval", "job_id": director_job_id}

    # Step 2: Tactician
    tactician_job_id = tactician_task(director_job_id)

    if auto_approve:
        job_store.approve_job(tactician_job_id)
        logger.info(f"Auto-approved Tactician job: {tactician_job_id}")
    else:
        logger.info(f"Tactician job {tactician_job_id} requires manual approval")
        return {"status": "pending_tactician_approval", "job_id": tactician_job_id}

    # Step 3: Weaver and Canonist (automated)
    tactician_output = job_store.get_job(tactician_job_id)
    if not tactician_output:
        raise ValueError(f"Tactician job {tactician_job_id} not found")
    chapter_text = weaver_task(tactician_job_id)
    final_results = await canonist_task(chapter_text, tactician_output.output_payload, story_id)

    logger.info("Full generation complete!")
    return final_results


# Utility functions for CLI integration
def get_pending_jobs() -> list[str]:
    """Get all pending job IDs for CLI review."""
    pending_jobs = job_store.get_pending_jobs()
    return [job.job_id for job in pending_jobs]


def get_job_details(job_id: str) -> Optional[dict]:
    """Get job details for CLI review."""
    job = job_store.get_job(job_id)
    if job:
        return {
            "job_id": job.job_id,
            "agent": job.agent,
            "status": job.status,
            "input_payload": job.input_payload,
            "output_payload": job.output_payload,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "feedback": job.feedback_history
        }
    return None


async def approve_job_and_continue(job_id: str, story_id: Optional[str] = None) -> str:
    """Approve a job and trigger the next flow step."""
    job = job_store.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job.status != "pending_approval":
        raise ValueError(f"Job {job_id} is not pending approval (status: {job.status})")

    job_store.approve_job(job_id)

    # Trigger next flow based on agent type
    if job.agent == "Director":
        return continue_generation_flow(job_id)
    elif job.agent == "Tactician":
        result = await finalize_generation_flow(job_id, story_id)
        return f"Chapter complete: {result['validated_text'][:100]}..."
    else:
        raise ValueError(f"Unknown agent type: {job.agent}")


def reject_job_with_feedback(job_id: str, feedback: str) -> str:
    """Reject a job with feedback and restart from the beginning."""
    job = job_store.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job.status != "pending_approval":
        raise ValueError(f"Job {job_id} is not pending approval (status: {job.status})")

    job_store.reject_job(job_id, feedback)

    # Restart from the beginning with feedback
    if job.agent == "Director":
        input_payload = job.input_payload.copy()
        input_payload["feedback"] = feedback
        import asyncio
        result = asyncio.run(initial_generation_flow(
            input_payload["chapter_seed"],
            input_payload.get("active_characters")
        ))
        return result
    elif job.agent == "Tactician":
        # Find the original director job and restart from there
        input_payload = job.input_payload.copy()
        input_payload["feedback"] = feedback
        # Would need to implement logic to find original director job
        # For now, just indicate restart needed
        return f"Job {job_id} rejected. Manual restart required."
    else:
        raise ValueError(f"Unknown agent type: {job.agent}")


if __name__ == "__main__":
    # Test the flow with auto-approval
    import asyncio
    result = asyncio.run(full_generation_flow(
        "A mysterious stranger arrives in a small mountain town during a thunderstorm.",
        auto_approve=True
    ))
    print(f"Generated chapter: {result['validated_text'][:200]}...")
    print(f"Story state: Chapter {result['story_state']['current_chapter']}")
