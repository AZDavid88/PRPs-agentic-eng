"""Prefect flows for narrative generation with HITL checkpoints."""

import asyncio
import time
from typing import Optional

from prefect import flow, get_run_logger, task
from prefect.tasks import exponential_backoff

from src.agents.librarian import LibrarianAgent
from src.agents.personas import CanonistAgent, DirectorAgent, TacticianAgent, WeaverAgent
from src.ingestion.pipeline import MaterialIngestionPipeline, PipelineProgressUpdate
from src.memory.qdrant import QdrantService
from src.models.librarian_models import MaterialAnalysisRequest
from src.models.material_models import MaterialClassification, MaterialIngestionRequest
from src.services.state_manager import StateManager
from src.workflows.jobs import JobStore


# Initialize services - lazy loading for testing
job_store = JobStore()
memory_service = None
state_manager = StateManager()

def _get_memory_service():
    """Lazy initialization of memory service for testing compatibility."""
    global memory_service
    if memory_service is None:
        memory_service = QdrantService()
    return memory_service


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
        context = await _get_memory_service().fetch_context_for_director(chapter_seed, active_characters)

        # Enhance context with catalyst if provided
        if catalyst:
            logger.info(f"Applying catalyst: {catalyst}")
            context_dict = context.model_dump()
            context_dict["catalyst"] = catalyst
            context = context.model_validate(context_dict)

        # Execute Director agent
        director = DirectorAgent()
        strategic_brief = await director.execute(chapter_seed, context.model_dump())

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


# === PHASE 1B: MATERIAL INGESTION WORKFLOWS ===

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def material_ingestion_task(
    materials: list[str],
    genre_context: str = "unknown",
    processing_mode: str = "pipeline",
    batch_size: int = 20,
    min_confidence_threshold: float = 0.7,
    additional_genres: Optional[list[str]] = None,
    custom_categories: Optional[list[str]] = None,
    story_id: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """Execute material ingestion pipeline and save result to JobStore for tracking.

    Args:
        materials: List of raw material content
        genre_context: Primary genre context for classification
        processing_mode: Processing mode (pipeline/agent/hybrid)
        batch_size: Batch size for processing
        min_confidence_threshold: Minimum confidence for classification
        additional_genres: Additional genre contexts
        custom_categories: Custom classification categories
        story_id: Optional story ID to associate materials with
        dry_run: If True, validate inputs without processing

    Returns:
        str: Job ID for the ingestion task
    """
    logger = get_run_logger()

    logger.info(f"Starting material ingestion: {len(materials)} materials in {processing_mode} mode")

    # Create job in JobStore
    job_id = job_store.create_job(
        agent="MaterialIngestion",  # Treated as agent for workflow consistency
        input_payload={
            "materials": materials,
            "genre_context": genre_context,
            "processing_mode": processing_mode,
            "batch_size": batch_size,
            "min_confidence_threshold": min_confidence_threshold,
            "additional_genres": additional_genres or [],
            "custom_categories": custom_categories or [],
            "story_id": story_id,
            "dry_run": dry_run
        }
    )

    try:
        if dry_run:
            # Dry run mode - validate inputs without processing
            logger.info("DRY RUN MODE: Validating material ingestion inputs")

            # Simulate validation
            mock_validation = {
                "materials_count": len(materials),
                "estimated_cost": len(materials) * 0.005,  # Pipeline mode estimate
                "genre_context": genre_context,
                "processing_mode": processing_mode,
                "dry_run": True,
                "validation_status": "passed"
            }

            job_store.update_job_as_pending(job_id, mock_validation)
            logger.info(f"Dry run material ingestion complete. Job ID: {job_id}")
            return job_id

        # Initialize pipeline
        pipeline = MaterialIngestionPipeline()

        # Create ingestion request
        request = MaterialIngestionRequest(
            materials=materials,
            genre_context=genre_context,
            processing_mode=processing_mode,
            batch_size=batch_size,
            min_confidence_threshold=min_confidence_threshold,
            additional_genres=additional_genres or [],
            custom_categories=custom_categories or [],
            story_id=story_id
        )

        # Progress callback for Prefect logging
        def progress_callback(update: PipelineProgressUpdate):
            logger.info(
                f"Ingestion Progress: {update.progress_percentage:.1f}% - "
                f"Stage: {update.stage} - {update.message}"
            )

        # Execute pipeline
        response = await pipeline.process_materials(request, progress_callback)

        # Save output and mark as pending approval
        job_store.update_job_as_pending(job_id, {
            "response": response.model_dump(),
            "status": "completed" if response.status == "completed" else "partial",
            "materials_processed": response.materials_processed,
            "processing_time": response.processing_time,
            "cost_estimate": response.cost_estimate,
            "average_confidence": response.average_confidence,
            "category_distribution": response.category_distribution
        })

        # Cleanup
        await pipeline.close()

        logger.info(
            f"Material ingestion complete. Job ID: {job_id} - "
            f"Processed: {response.materials_processed}/{len(materials)} materials"
        )
        return job_id

    except Exception as e:
        logger.error(f"Material ingestion task failed: {str(e)}")

        # Update job with error status
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "status": "failed",
            "materials_processed": 0
        })
        raise


@flow(name="Material Ingestion Flow", log_prints=True)
async def material_ingestion_flow(
    materials: list[str],
    genre_context: str = "unknown",
    processing_mode: str = "pipeline",
    batch_size: int = 20,
    story_id: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """Complete material ingestion workflow with job tracking.

    Args:
        materials: List of raw material content
        genre_context: Primary genre context for classification
        processing_mode: Processing mode (pipeline/agent/hybrid)
        batch_size: Batch size for processing
        story_id: Optional story ID to associate materials with
        dry_run: If True, validate inputs without processing

    Returns:
        str: Ingestion job ID for tracking
    """
    logger = get_run_logger()

    logger.info(f"Starting material ingestion flow: {len(materials)} materials")
    logger.info(f"Genre: {genre_context}, Mode: {processing_mode}, Batch size: {batch_size}")

    # Execute ingestion task
    ingestion_job_id = await material_ingestion_task(
        materials=materials,
        genre_context=genre_context,
        processing_mode=processing_mode,
        batch_size=batch_size,
        story_id=story_id,
        dry_run=dry_run
    )

    if dry_run:
        logger.info(f"DRY RUN material ingestion complete. Job ID: {ingestion_job_id}")
        logger.info("DRY RUN MODE - No actual processing performed")
    else:
        logger.info(f"Material ingestion complete. Job ID: {ingestion_job_id}")
        logger.info("Materials are now available in the story knowledge base")
        if story_id:
            logger.info(f"Materials associated with story: {story_id}")

    return ingestion_job_id


@flow(name="Bulk Material Ingestion Flow", log_prints=True)
async def bulk_material_ingestion_flow(
    material_batches: list[dict],
    default_genre: str = "unknown",
    concurrent_batches: int = 3,
    story_id: Optional[str] = None
) -> list[str]:
    """Process multiple material batches concurrently for large-scale ingestion.

    Args:
        material_batches: List of batch configs, each with 'materials', 'genre', etc.
        default_genre: Default genre if not specified in batch
        concurrent_batches: Maximum concurrent batch processing
        story_id: Optional story ID to associate all materials with

    Returns:
        list[str]: List of job IDs for all ingestion tasks
    """
    logger = get_run_logger()

    logger.info(f"Starting bulk material ingestion: {len(material_batches)} batches")
    logger.info(f"Concurrent limit: {concurrent_batches}")

    job_ids = []

    # Process batches in chunks to respect concurrency limits
    for i in range(0, len(material_batches), concurrent_batches):
        batch_chunk = material_batches[i:i + concurrent_batches]

        logger.info(f"Processing batch chunk {i//concurrent_batches + 1}: {len(batch_chunk)} batches")

        # Process current chunk concurrently
        chunk_tasks = []
        for batch_config in batch_chunk:
            materials = batch_config.get('materials', [])
            genre = batch_config.get('genre', default_genre)
            mode = batch_config.get('processing_mode', 'pipeline')
            batch_size = batch_config.get('batch_size', 20)

            if materials:  # Only process non-empty batches
                task = material_ingestion_task(
                    materials=materials,
                    genre_context=genre,
                    processing_mode=mode,
                    batch_size=batch_size,
                    story_id=story_id
                )
                chunk_tasks.append(task)

        # Wait for current chunk to complete
        if chunk_tasks:
            chunk_job_ids = await asyncio.gather(*chunk_tasks)
            job_ids.extend(chunk_job_ids)

            logger.info(f"Chunk complete: {len(chunk_job_ids)} jobs finished")

    logger.info(f"Bulk material ingestion complete: {len(job_ids)} total jobs")
    logger.info("All materials are now available in the story knowledge base")

    return job_ids


# === PHASE 2A: LIBRARIAN AGENT WORKFLOWS ===

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def librarian_analysis_task(
    materials: list[MaterialClassification],
    analysis_depth: str = "standard",
    enable_cross_references: bool = True,
    enable_quality_assessment: bool = True,
    concurrent_limit: int = 10,
    story_id: Optional[str] = None,
    dry_run: bool = False,
    max_material_size: int = 50000,
    timeout_minutes: int = 30
) -> str:
    """Execute LibrarianAgent material analysis with JobStore integration.

    Args:
        materials: List of MaterialClassification objects to analyze
        analysis_depth: Analysis depth (quick, standard, comprehensive)
        enable_cross_references: Generate cross-references between materials
        enable_quality_assessment: Perform quality assessment on materials
        concurrent_limit: Maximum concurrent material processing (1-20)
        story_id: Optional story ID to associate analysis with
        dry_run: If True, validate inputs without actual processing
        max_material_size: Maximum character limit per material (security)
        timeout_minutes: Overall task timeout limit

    Returns:
        str: Job ID for the LibrarianAgent analysis task

    Raises:
        ValueError: Invalid input parameters or material validation failures
        LibrarianError: LibrarianAgent processing failures
        TimeoutError: Task exceeds timeout limit
    """
    logger = get_run_logger()

    # Input validation and sanitization
    if not materials:
        raise ValueError("Materials list cannot be empty")

    if not 1 <= concurrent_limit <= 20:
        raise ValueError("Concurrent limit must be between 1 and 20")

    if analysis_depth not in ["quick", "standard", "comprehensive"]:
        raise ValueError("Analysis depth must be 'quick', 'standard', or 'comprehensive'")

    # Security validation - check material sizes
    oversized_materials = []
    for i, material in enumerate(materials):
        if len(material.content) > max_material_size:
            oversized_materials.append((i, material.id, len(material.content)))

    if oversized_materials:
        logger.warning(f"Found {len(oversized_materials)} oversized materials")
        for idx, mat_id, size in oversized_materials:
            logger.warning(f"Material {mat_id} at index {idx}: {size} chars (limit: {max_material_size})")

    logger.info(f"Starting LibrarianAgent analysis: {len(materials)} materials")
    logger.info(f"Config: depth={analysis_depth}, cross_refs={enable_cross_references}, "
                f"quality={enable_quality_assessment}, concurrent={concurrent_limit}")

    # Create job in JobStore
    job_id = job_store.create_job(
        agent="LibrarianAgent",
        input_payload={
            "materials_count": len(materials),
            "material_ids": [mat.id for mat in materials],
            "analysis_depth": analysis_depth,
            "enable_cross_references": enable_cross_references,
            "enable_quality_assessment": enable_quality_assessment,
            "concurrent_limit": concurrent_limit,
            "story_id": story_id,
            "dry_run": dry_run,
            "max_material_size": max_material_size,
            "timeout_minutes": timeout_minutes
        }
    )

    try:
        if dry_run:
            # Dry run mode - validate inputs without processing
            logger.info("DRY RUN MODE: Validating LibrarianAgent analysis inputs")

            # Simulate analysis validation
            mock_analysis = {
                "materials_count": len(materials),
                "estimated_processing_time": len(materials) * 2.5,  # 2.5 seconds per material
                "estimated_embedding_cost": len(materials) * 0.01,  # $0.01 per material
                "analysis_depth": analysis_depth,
                "concurrent_limit": concurrent_limit,
                "oversized_materials": len(oversized_materials),
                "validation_status": "passed" if not oversized_materials else "warnings",
                "dry_run": True
            }

            job_store.update_job_as_pending(job_id, mock_analysis)
            logger.info(f"Dry run LibrarianAgent analysis complete. Job ID: {job_id}")
            return job_id

        # Initialize LibrarianAgent
        librarian = LibrarianAgent(memory_service=_get_memory_service())

        # Create analysis request
        analysis_request = MaterialAnalysisRequest(
            classifications=materials,
            analysis_depth=analysis_depth,
            enable_cross_references=enable_cross_references,
            enable_quality_assessment=enable_quality_assessment,
            story_context=f"Story ID: {story_id}" if story_id else None,
            concurrent_limit=concurrent_limit
        )

        # Execute LibrarianAgent analysis with timeout
        async def run_analysis_with_timeout():
            return await librarian.analyze_materials(analysis_request)

        try:
            analysis_response = await asyncio.wait_for(
                run_analysis_with_timeout(),
                timeout=timeout_minutes * 60
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"LibrarianAgent analysis exceeded {timeout_minutes} minute timeout")

        # Process results and prepare job output
        job_output = {
            "analysis_response": analysis_response.model_dump(),
            "summary": {
                "materials_processed": analysis_response.successful_count,
                "materials_failed": analysis_response.failed_count,
                "success_rate": analysis_response.get_success_rate(),
                "processing_time": analysis_response.processing_time,
                "cross_references_generated": analysis_response.cross_references_generated,
                "quality_issues_found": analysis_response.quality_issues_found
            },
            "metrics": analysis_response.metrics.model_dump(),
            "story_id": story_id,
            "timestamp": time.time()
        }

        # Store results and mark as pending approval
        job_store.update_job_as_pending(job_id, job_output)

        # Cleanup
        await librarian.close()

        logger.info(
            f"LibrarianAgent analysis complete. Job ID: {job_id} - "
            f"Processed: {analysis_response.successful_count}/{len(materials)} materials, "
            f"Success rate: {analysis_response.get_success_rate():.1f}%, "
            f"Processing time: {analysis_response.processing_time:.2f}s"
        )

        return job_id

    except Exception as e:
        logger.error(f"LibrarianAgent analysis task failed: {str(e)}")

        # Update job with error status
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "failed",
            "materials_processed": 0,
            "timestamp": time.time()
        })
        raise


@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def enhanced_material_ingestion_task(
    materials: list[str],
    genre_context: str = "unknown",
    processing_mode: str = "pipeline",
    enable_librarian_analysis: bool = False,
    librarian_analysis_depth: str = "standard",
    librarian_concurrent_limit: int = 5,
    batch_size: int = 20,
    min_confidence_threshold: float = 0.7,
    additional_genres: Optional[list[str]] = None,
    custom_categories: Optional[list[str]] = None,
    story_id: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """Enhanced material ingestion with optional LibrarianAgent analysis.

    This extends the existing material_ingestion_task to optionally include
    LibrarianAgent analysis after successful material classification.

    Args:
        materials: List of raw material content
        genre_context: Primary genre context for classification
        processing_mode: Processing mode (pipeline/agent/hybrid)
        enable_librarian_analysis: Enable post-ingestion LibrarianAgent analysis
        librarian_analysis_depth: Depth for LibrarianAgent analysis
        librarian_concurrent_limit: Concurrent limit for LibrarianAgent processing
        batch_size: Batch size for initial material processing
        min_confidence_threshold: Minimum confidence for classification
        additional_genres: Additional genre contexts
        custom_categories: Custom classification categories
        story_id: Optional story ID to associate materials with
        dry_run: If True, validate inputs without processing

    Returns:
        str: Job ID for the enhanced ingestion task
    """
    logger = get_run_logger()

    logger.info(f"Starting enhanced material ingestion: {len(materials)} materials")
    logger.info(f"LibrarianAgent analysis: {'enabled' if enable_librarian_analysis else 'disabled'}")

    # Create job in JobStore for enhanced ingestion
    job_id = job_store.create_job(
        agent="EnhancedMaterialIngestion",
        input_payload={
            "materials_count": len(materials),
            "genre_context": genre_context,
            "processing_mode": processing_mode,
            "enable_librarian_analysis": enable_librarian_analysis,
            "librarian_config": {
                "analysis_depth": librarian_analysis_depth,
                "concurrent_limit": librarian_concurrent_limit
            } if enable_librarian_analysis else None,
            "batch_size": batch_size,
            "story_id": story_id,
            "dry_run": dry_run
        }
    )

    try:
        # Phase 1: Standard material ingestion
        logger.info("Phase 1: Executing standard material ingestion")

        ingestion_job_id = await material_ingestion_task(
            materials=materials,
            genre_context=genre_context,
            processing_mode=processing_mode,
            batch_size=batch_size,
            min_confidence_threshold=min_confidence_threshold,
            additional_genres=additional_genres,
            custom_categories=custom_categories,
            story_id=story_id,
            dry_run=dry_run
        )

        # Get ingestion results
        ingestion_job = job_store.get_job(ingestion_job_id)
        if not ingestion_job or ingestion_job.status != "pending_approval":
            raise ValueError(f"Material ingestion failed or requires approval: {ingestion_job_id}")

        enhanced_output = {
            "phase_1_ingestion": {
                "job_id": ingestion_job_id,
                "status": "completed",
                "results": ingestion_job.output_payload
            }
        }

        # Phase 2: Optional LibrarianAgent analysis
        if enable_librarian_analysis and not dry_run:
            logger.info("Phase 2: Executing LibrarianAgent analysis")

            # Extract MaterialClassification objects from ingestion results
            ingestion_response = ingestion_job.output_payload.get("response", {})
            classified_materials = ingestion_response.get("classifications", [])

            if classified_materials:
                # Convert to MaterialClassification objects
                material_classifications = [
                    MaterialClassification.model_validate(mat_data)
                    for mat_data in classified_materials
                ]

                # Execute LibrarianAgent analysis
                librarian_job_id = await librarian_analysis_task(
                    materials=material_classifications,
                    analysis_depth=librarian_analysis_depth,
                    concurrent_limit=librarian_concurrent_limit,
                    story_id=story_id,
                    dry_run=False
                )

                enhanced_output["phase_2_librarian"] = {
                    "job_id": librarian_job_id,
                    "status": "completed",
                    "materials_analyzed": len(material_classifications)
                }

                logger.info(f"LibrarianAgent analysis initiated: {librarian_job_id}")
            else:
                enhanced_output["phase_2_librarian"] = {
                    "status": "skipped",
                    "reason": "No classified materials available for analysis"
                }
        else:
            enhanced_output["phase_2_librarian"] = {
                "status": "disabled" if not enable_librarian_analysis else "skipped_dry_run"
            }

        # Update job with combined results
        job_store.update_job_as_pending(job_id, enhanced_output)

        logger.info(f"Enhanced material ingestion complete. Job ID: {job_id}")
        return job_id

    except Exception as e:
        logger.error(f"Enhanced material ingestion failed: {str(e)}")

        # Update job with error status
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "failed"
        })
        raise


@flow(name="LibrarianAgent Analysis Flow", log_prints=True)
async def librarian_analysis_flow(
    materials: list[MaterialClassification],
    analysis_depth: str = "standard",
    enable_cross_references: bool = True,
    enable_quality_assessment: bool = True,
    concurrent_limit: int = 10,
    story_id: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """Complete LibrarianAgent analysis workflow with job tracking.

    Args:
        materials: List of MaterialClassification objects to analyze
        analysis_depth: Analysis depth (quick, standard, comprehensive)
        enable_cross_references: Generate cross-references between materials
        enable_quality_assessment: Perform quality assessment on materials
        concurrent_limit: Maximum concurrent material processing
        story_id: Optional story ID to associate analysis with
        dry_run: If True, validate inputs without processing

    Returns:
        str: LibrarianAgent analysis job ID for tracking
    """
    logger = get_run_logger()

    logger.info(f"Starting LibrarianAgent analysis flow: {len(materials)} materials")
    logger.info(f"Analysis depth: {analysis_depth}, Cross-refs: {enable_cross_references}")
    logger.info(f"Quality assessment: {enable_quality_assessment}, Concurrent: {concurrent_limit}")

    # Execute LibrarianAgent analysis task
    analysis_job_id = await librarian_analysis_task(
        materials=materials,
        analysis_depth=analysis_depth,
        enable_cross_references=enable_cross_references,
        enable_quality_assessment=enable_quality_assessment,
        concurrent_limit=concurrent_limit,
        story_id=story_id,
        dry_run=dry_run
    )

    if dry_run:
        logger.info(f"DRY RUN LibrarianAgent analysis complete. Job ID: {analysis_job_id}")
        logger.info("DRY RUN MODE - No actual processing performed")
    else:
        logger.info(f"LibrarianAgent analysis complete. Job ID: {analysis_job_id}")
        logger.info("HUMAN REVIEW REQUIRED for LibrarianAgent analysis")
        logger.info(f"Use CLI to review results: factory.py review {analysis_job_id}")

    return analysis_job_id


@flow(name="Enhanced Material Ingestion Flow", log_prints=True)
async def enhanced_material_ingestion_flow(
    materials: list[str],
    genre_context: str = "unknown",
    processing_mode: str = "pipeline",
    enable_librarian_analysis: bool = True,
    librarian_analysis_depth: str = "standard",
    batch_size: int = 20,
    story_id: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """Enhanced material ingestion workflow with optional LibrarianAgent analysis.

    Args:
        materials: List of raw material content
        genre_context: Primary genre context for classification
        processing_mode: Processing mode (pipeline/agent/hybrid)
        enable_librarian_analysis: Enable post-ingestion LibrarianAgent analysis
        librarian_analysis_depth: Depth for LibrarianAgent analysis
        batch_size: Batch size for processing
        story_id: Optional story ID to associate materials with
        dry_run: If True, validate inputs without processing

    Returns:
        str: Enhanced ingestion job ID for tracking
    """
    logger = get_run_logger()

    logger.info(f"Starting enhanced material ingestion flow: {len(materials)} materials")
    logger.info(f"Genre: {genre_context}, Mode: {processing_mode}, Batch size: {batch_size}")
    logger.info(f"LibrarianAgent analysis: {'enabled' if enable_librarian_analysis else 'disabled'}")

    # Execute enhanced ingestion task
    enhanced_job_id = await enhanced_material_ingestion_task(
        materials=materials,
        genre_context=genre_context,
        processing_mode=processing_mode,
        enable_librarian_analysis=enable_librarian_analysis,
        librarian_analysis_depth=librarian_analysis_depth,
        batch_size=batch_size,
        story_id=story_id,
        dry_run=dry_run
    )

    if dry_run:
        logger.info(f"DRY RUN enhanced material ingestion complete. Job ID: {enhanced_job_id}")
        logger.info("DRY RUN MODE - No actual processing performed")
    else:
        logger.info(f"Enhanced material ingestion complete. Job ID: {enhanced_job_id}")
        logger.info("Materials processed and analyzed (if enabled)")
        if story_id:
            logger.info(f"Materials associated with story: {story_id}")
        if enable_librarian_analysis:
            logger.info("LibrarianAgent analysis results available for review")

    return enhanced_job_id


# === PHASE 2B: AGENT ORCHESTRATION WORKFLOWS ===

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def agent_orchestration_task(
    job_id: str,
    agent_type: str = "librarian",
    analysis_depth: str = "standard",
    session_id: Optional[str] = None,
    client_type: str = "openai",
    timeout_minutes: int = 15,
    save_session: bool = False,
    dry_run: bool = False
) -> str:
    """Execute agent analysis using the orchestration service.

    Args:
        job_id: Material ingestion job ID to analyze
        agent_type: Type of agent to use (librarian, director, etc.)
        analysis_depth: Analysis depth (quick, standard, comprehensive)
        session_id: Optional session ID for tracking
        client_type: LLM client type (openai, gemini)
        timeout_minutes: Timeout in minutes for agent execution
        save_session: Whether to save the agent session for replay
        dry_run: If True, validate inputs without processing

    Returns:
        str: Agent orchestration job ID for tracking

    Raises:
        LibrarianError: Agent processing failures
        TimeoutError: Analysis timeout
    """
    import uuid

    from src.agents.orchestration import get_orchestration_service
    from src.workflows.jobs import JobStore

    logger = get_run_logger()
    job_store = JobStore()

    # Generate orchestration job ID
    orchestration_job_id = f"agent_orch_{uuid.uuid4().hex[:8]}"

    logger.info(f"Starting agent orchestration: {agent_type} for job {job_id}")
    logger.info(f"Session: {session_id}, Client: {client_type}, Timeout: {timeout_minutes}min")

    # Store initial job info
    orchestration_job_id = job_store.create_job(
        agent="AgentOrchestration",
        input_payload={
            "source_job_id": job_id,
            "agent_type": agent_type,
            "analysis_depth": analysis_depth,
            "session_id": session_id,
            "client_type": client_type,
            "timeout_minutes": timeout_minutes,
            "save_session": save_session,
            "dry_run": dry_run
        }
    )

    try:
        if dry_run:
            # Dry run mode - validate inputs without processing
            logger.info("DRY RUN MODE: Validating agent orchestration inputs")

            # Get source job to validate
            source_job = job_store.get_job(job_id)
            if not source_job:
                raise ValueError(f"Source job {job_id} not found")

            # Simulate orchestration validation
            mock_orchestration = {
                "source_job_id": job_id,
                "agent_type": agent_type,
                "estimated_processing_time": 120,  # 2 minutes
                "session_id": session_id or f"dry_run_{uuid.uuid4().hex[:8]}",
                "client_type": client_type,
                "validation_status": "passed",
                "dry_run": True
            }

            job_store.update_job_as_pending(orchestration_job_id, mock_orchestration)
            logger.info(f"Dry run agent orchestration complete. Job ID: {orchestration_job_id}")
            return orchestration_job_id

        # Get source job data
        source_job = job_store.get_job(job_id)
        if not source_job:
            raise ValueError(f"Source job {job_id} not found")

        # Extract materials from source job
        source_data = source_job.get("data", {})
        materials = source_data.get("materials", [])

        if not materials:
            raise ValueError(f"No materials found in source job {job_id}")

        # Initialize orchestration service
        orchestration = get_orchestration_service()

        # Generate session ID if not provided
        actual_session_id = session_id or f"analysis_{uuid.uuid4().hex[:8]}"

        # Initialize agent
        agent_id = await orchestration.initialize_agent(
            agent_type=agent_type,
            client_type=client_type,
            session_id=actual_session_id
        )

        logger.info(f"Agent {agent_type}:{agent_id} initialized successfully")

        # Prepare request data based on agent type
        if agent_type == "librarian":
            request_data = {
                "materials": materials,
                "analysis_config": {
                    "analysis_depth": analysis_depth,
                    "enable_cross_references": True,
                    "enable_quality_assessment": True
                }
            }
        else:
            # For other agent types, adapt request data as needed
            request_data = {"materials": materials}

        # Execute agent with timeout
        async def run_agent_with_timeout():
            return await orchestration.execute_agent(
                agent_id=agent_id,
                request_data=request_data,
                context={"job_id": job_id, "session_id": actual_session_id}
            )

        try:
            agent_result = await asyncio.wait_for(
                run_agent_with_timeout(),
                timeout=timeout_minutes * 60
            )
        except asyncio.TimeoutError:
            await orchestration.shutdown_agent(agent_id)
            raise TimeoutError(f"Agent {agent_type} execution exceeded {timeout_minutes} minute timeout")

        # Process results and prepare job output
        orchestration_output = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "session_id": actual_session_id,
            "client_type": client_type,
            "analysis_result": agent_result,
            "source_job_id": job_id,
            "materials_processed": len(materials),
            "processing_time": time.time(),
            "save_session": save_session
        }

        # Get orchestration status for additional context
        orchestration_status = await orchestration.get_orchestration_status()
        orchestration_output["orchestration_status"] = orchestration_status

        # Clean up agent if not saving session
        if not save_session:
            await orchestration.shutdown_agent(agent_id)
            logger.info(f"Agent {agent_id} shut down (session not saved)")
        else:
            logger.info(f"Agent session {actual_session_id} saved for replay")

        # Update job as completed
        job_store.update_job_as_completed(orchestration_job_id, orchestration_output)

        logger.info(
            f"Agent orchestration complete. Job ID: {orchestration_job_id} - "
            f"Agent: {agent_type}, Materials: {len(materials)}, Session: {actual_session_id}"
        )

        return orchestration_job_id

    except Exception as e:
        logger.error(f"Agent orchestration task failed: {str(e)}")

        # Update job as failed
        job_store.update_job_as_failed(
            orchestration_job_id,
            error_message=str(e),
            error_details={"agent_type": agent_type, "source_job_id": job_id}
        )

        # Try to clean up any initialized agents
        try:
            orchestration = get_orchestration_service()
            orchestration_status = await orchestration.get_orchestration_status()
            active_agents = orchestration_status.get("active_agents", {})

            for _agent_type_key, agent_ids in active_agents.items():
                for agent_id in agent_ids:
                    try:
                        await orchestration.shutdown_agent(agent_id)
                        logger.info(f"Cleaned up agent {agent_id} after failure")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup agent {agent_id}: {cleanup_error}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to perform orchestration cleanup: {cleanup_error}")

        raise


@flow(name="Agent Orchestration Flow", log_prints=True)
async def agent_orchestration_flow(
    job_id: str,
    agent_type: str = "librarian",
    analysis_depth: str = "standard",
    session_id: Optional[str] = None,
    client_type: str = "openai",
    timeout_minutes: int = 15,
    save_session: bool = False,
    dry_run: bool = False
) -> str:
    """Complete agent orchestration workflow with comprehensive lifecycle management.

    Args:
        job_id: Material ingestion job ID to analyze
        agent_type: Type of agent to use (librarian, director, etc.)
        analysis_depth: Analysis depth (quick, standard, comprehensive)
        session_id: Optional session ID for tracking
        client_type: LLM client type (openai, gemini)
        timeout_minutes: Timeout in minutes for agent execution
        save_session: Whether to save the agent session for replay
        dry_run: If True, validate inputs without processing

    Returns:
        str: Agent orchestration job ID for tracking
    """
    logger = get_run_logger()

    logger.info(f"Starting agent orchestration flow for job: {job_id}")
    logger.info(f"Agent: {agent_type}, Depth: {analysis_depth}, Client: {client_type}")
    logger.info(f"Session: {session_id}, Save: {save_session}, Timeout: {timeout_minutes}min")

    # Execute agent orchestration task
    orchestration_job_id = await agent_orchestration_task(
        job_id=job_id,
        agent_type=agent_type,
        analysis_depth=analysis_depth,
        session_id=session_id,
        client_type=client_type,
        timeout_minutes=timeout_minutes,
        save_session=save_session,
        dry_run=dry_run
    )

    if dry_run:
        logger.info(f"DRY RUN agent orchestration complete. Job ID: {orchestration_job_id}")
        logger.info("DRY RUN MODE - No actual agent processing performed")
    else:
        logger.info(f"Agent orchestration complete. Job ID: {orchestration_job_id}")
        logger.info("Agent-based analysis complete with full lifecycle management")
        logger.info(f"Use CLI to review results: factory review {orchestration_job_id}")
        if save_session:
            logger.info(f"Agent session saved - replay with: factory agent-session replay --session {session_id}")

    return orchestration_job_id


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
        input_payload = job.input_payload.model_copy()
        input_payload["feedback"] = feedback
        import asyncio
        result = asyncio.run(initial_generation_flow(
            input_payload["chapter_seed"],
            input_payload.get("active_characters")
        ))
        return result
    elif job.agent == "Tactician":
        # Find the original director job and restart from there
        input_payload = job.input_payload.model_copy()
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
