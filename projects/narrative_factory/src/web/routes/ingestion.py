"""
Material Ingestion Routes for FastAPI Web Interface.

Task 11: Implement Upload Routes
- Multi-file upload endpoint
- Progress tracking endpoint  
- Status monitoring endpoint
- Results retrieval endpoint
"""

import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.ingestion.pipeline import MaterialIngestionPipeline, PipelineProgressUpdate
from src.logger import get_logger
from src.models.material_models import MaterialIngestionRequest, MaterialIngestionResponse


logger = get_logger(__name__)

# Router for ingestion endpoints
router = APIRouter()

# In-memory storage for job tracking (in production, use Redis or database)
active_jobs: Dict[str, Dict[str, Any]] = {}
job_results: Dict[str, MaterialIngestionResponse] = {}

class UploadResponse(BaseModel):
    """Response model for file upload."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Upload status")
    files_count: int = Field(..., description="Number of files uploaded")
    message: str = Field(..., description="Status message")

class ProgressResponse(BaseModel):
    """Response model for progress tracking."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    progress_percentage: float = Field(..., description="Progress percentage")
    current_stage: str = Field(..., description="Current processing stage")
    materials_processed: int = Field(..., description="Materials processed")
    materials_remaining: int = Field(..., description="Materials remaining")
    estimated_time_remaining: float = Field(..., description="ETA in seconds")
    message: Optional[str] = Field(None, description="Current status message")

class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")
    files_count: int = Field(..., description="Number of files")
    processing_mode: str = Field(..., description="Processing mode")
    genre_context: str = Field(..., description="Genre context")

def get_pipeline() -> MaterialIngestionPipeline:
    """Dependency to get pipeline instance."""
    return MaterialIngestionPipeline()

def progress_callback_factory(job_id: str) -> Callable[[PipelineProgressUpdate], None]:
    """Factory function to create progress callback for specific job."""
    def progress_callback(update: PipelineProgressUpdate) -> None:
        """Update job progress in memory store."""
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "progress_percentage": update.progress_percentage,
                "current_stage": update.stage,
                "materials_processed": update.materials_processed,
                "materials_remaining": update.materials_remaining,
                "estimated_time_remaining": update.estimated_time_remaining,
                "message": update.message,
                "updated_at": datetime.now()
            })
    return progress_callback

@router.post("/upload", response_model=UploadResponse)
async def upload_materials(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Material files to upload"),
    genre_context: str = Form("unknown", description="Genre context for classification"),
    processing_mode: str = Form("pipeline", description="Processing mode: pipeline, agent, or hybrid"),
    additional_genres: Optional[str] = Form(None, description="Additional genres (comma-separated)"),
    batch_size: int = Form(20, description="Batch size for processing"),
    min_confidence_threshold: float = Form(0.7, description="Minimum confidence threshold"),
    enable_cross_references: bool = Form(True, description="Enable cross-reference generation"),
    pipeline: MaterialIngestionPipeline = Depends(get_pipeline)
) -> UploadResponse:
    """
    Upload and process multiple material files.
    
    Supports various file formats and processing modes.
    Returns immediately with job ID for tracking progress.
    """
    try:
        # Validate inputs
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 files per upload")

        valid_modes = ["pipeline", "agent", "hybrid"]
        if processing_mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid processing mode. Must be one of: {valid_modes}"
            )

        # Generate job ID
        job_id = f"ingestion_{uuid.uuid4().hex[:8]}"

        # Process files and extract content
        materials = []
        uploaded_files = []

        for file in files:
            # Validate file type
            if not file.filename:
                continue

            # Read file content
            content = await file.read()

            # Handle different file types
            if file.filename.endswith(('.txt', '.md')):
                text_content = content.decode('utf-8')
            elif file.filename.endswith('.json'):
                # Handle JSON files (could contain structured material data)
                import json
                try:
                    json_data = json.loads(content.decode('utf-8'))
                    if isinstance(json_data, dict) and 'content' in json_data:
                        text_content = json_data['content']
                    else:
                        text_content = json.dumps(json_data, indent=2)
                except json.JSONDecodeError:
                    text_content = content.decode('utf-8')
            else:
                # Try to decode as text
                try:
                    text_content = content.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"Skipping file {file.filename} - not a text file")
                    continue

            materials.append(text_content)
            uploaded_files.append({
                "filename": file.filename,
                "size": len(content),
                "content_length": len(text_content)
            })

        if not materials:
            raise HTTPException(status_code=400, detail="No valid text files found")

        # Parse additional genres
        additional_genres_list = []
        if additional_genres:
            additional_genres_list = [g.strip() for g in additional_genres.split(',') if g.strip()]
        
        # Cast processing_mode to proper Literal type (already validated above)
        validated_mode: Literal["pipeline", "agent", "hybrid"] = processing_mode  # type: ignore
        
        # Create ingestion request
        request = MaterialIngestionRequest(
            materials=materials,
            genre_context=genre_context,
            processing_mode=validated_mode,
            additional_genres=additional_genres_list,
            custom_categories=None,
            batch_size=batch_size,
            min_confidence_threshold=min_confidence_threshold,
            enable_cross_references=enable_cross_references,
            enable_progressive_disclosure=True,
            story_id=None,
            user_id=None
        )

        # Store job metadata
        active_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "files_count": len(materials),
            "files": uploaded_files,
            "processing_mode": processing_mode,
            "genre_context": genre_context,
            "progress_percentage": 0.0,
            "current_stage": "queued",
            "materials_processed": 0,
            "materials_remaining": len(materials),
            "estimated_time_remaining": 0.0,
            "message": "Job queued for processing"
        }

        # Start background processing
        background_tasks.add_task(
            process_materials_background,
            job_id,
            request,
            pipeline
        )

        logger.info(f"Started ingestion job {job_id} with {len(materials)} materials")

        return UploadResponse(
            job_id=job_id,
            status="queued",
            files_count=len(materials),
            message=f"Successfully uploaded {len(materials)} files. Processing started."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def process_materials_background(
    job_id: str,
    request: MaterialIngestionRequest,
    pipeline: MaterialIngestionPipeline
) -> None:
    """Background task to process materials."""
    try:
        # Update job status
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "status": "processing",
                "updated_at": datetime.now(),
                "message": "Processing materials..."
            })

        # Create progress callback
        progress_callback = progress_callback_factory(job_id)

        # Process materials
        response = await pipeline.process_materials(request, progress_callback)

        # Store results
        job_results[job_id] = response

        # Update job status
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "status": "completed",
                "updated_at": datetime.now(),
                "progress_percentage": 100.0,
                "current_stage": "completed",
                "message": f"Processing completed: {response.materials_processed} materials processed"
            })

        logger.info(f"Completed ingestion job {job_id}: {response.materials_processed} materials processed")

    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")

        # Update job status with error
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "status": "failed",
                "updated_at": datetime.now(),
                "message": f"Processing failed: {str(e)}"
            })

    finally:
        # Cleanup pipeline resources
        try:
            await pipeline.close()
        except Exception as e:
            logger.warning(f"Error closing pipeline for job {job_id}: {e}")

@router.get("/progress/{job_id}", response_model=ProgressResponse)
async def get_progress(job_id: str) -> ProgressResponse:
    """
    Get processing progress for a specific job.
    
    Args:
        job_id: The job identifier from upload response
        
    Returns:
        Current progress information
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = active_jobs[job_id]

    return ProgressResponse(
        job_id=job_id,
        status=job_data["status"],
        progress_percentage=job_data["progress_percentage"],
        current_stage=job_data["current_stage"],
        materials_processed=job_data["materials_processed"],
        materials_remaining=job_data["materials_remaining"],
        estimated_time_remaining=job_data["estimated_time_remaining"],
        message=job_data["message"]
    )

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get detailed status information for a specific job.
    
    Args:
        job_id: The job identifier from upload response
        
    Returns:
        Detailed job status information
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = active_jobs[job_id]

    return JobStatusResponse(
        job_id=job_id,
        status=job_data["status"],
        created_at=job_data["created_at"],
        updated_at=job_data["updated_at"],
        files_count=job_data["files_count"],
        processing_mode=job_data["processing_mode"],
        genre_context=job_data["genre_context"]
    )

@router.get("/results/{job_id}")
async def get_results(job_id: str) -> dict[str, Any]:
    """
    Get processing results for a completed job.
    
    Args:
        job_id: The job identifier from upload response
        
    Returns:
        Complete processing results and metadata
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = active_jobs[job_id]

    if job_data["status"] not in ["completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Job is still {job_data['status']}. Results not yet available."
        )

    if job_id not in job_results:
        # Return error information if job failed
        return {
            "job_id": job_id,
            "status": job_data["status"],
            "error": job_data.get("message", "Unknown error"),
            "created_at": job_data["created_at"],
            "updated_at": job_data["updated_at"]
        }

    # Return successful results
    result = job_results[job_id]

    return {
        "job_id": job_id,
        "status": job_data["status"],
        "results": {
            "materials_processed": result.materials_processed,
            "processing_time": result.processing_time,
            "cost_estimate": result.cost_estimate,
            "average_confidence": result.average_confidence,
            "category_distribution": result.category_distribution,
            "complexity_distribution": result.complexity_distribution,
            "embedding_cache_hits": result.embedding_cache_hits,
            "cross_references_identified": result.cross_references_identified
        },
        "classifications": [
            {
                "material_id": c.material_id,
                "primary_category": c.primary_category,
                "secondary_categories": c.secondary_categories,
                "genre_context": c.genre_context,
                "complexity_level": c.complexity_level,
                "extracted_entities": c.extracted_entities,
                "spoiler_risk": c.spoiler_risk,
                "temporal_scope": c.temporal_scope
            } for c in result.classifications
        ] if result.classifications else [],
        "failed_materials": result.failed_materials,
        "errors": result.errors,
        "created_at": job_data["created_at"],
        "updated_at": job_data["updated_at"]
    }

@router.get("/jobs")
async def list_jobs(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """
    List all jobs with basic information.
    
    Args:
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        
    Returns:
        List of job summaries
    """
    # Sort jobs by creation time (newest first)
    sorted_jobs = sorted(
        active_jobs.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )

    # Apply pagination
    paginated_jobs = sorted_jobs[offset:offset + limit]

    return {
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "files_count": job["files_count"],
                "processing_mode": job["processing_mode"],
                "genre_context": job["genre_context"],
                "progress_percentage": job["progress_percentage"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"]
            }
            for job in paginated_jobs
        ],
        "total": len(active_jobs),
        "limit": limit,
        "offset": offset
    }

@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, str]:
    """
    Cancel a running job or delete job data.
    
    Args:
        job_id: The job identifier to cancel/delete
        
    Returns:
        Cancellation status
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = active_jobs[job_id]

    # If job is still running, mark as cancelled
    if job_data["status"] in ["queued", "processing"]:
        active_jobs[job_id].update({
            "status": "cancelled",
            "updated_at": datetime.now(),
            "message": "Job cancelled by user"
        })

        logger.info(f"Cancelled job {job_id}")
        return {"message": f"Job {job_id} cancelled successfully"}

    # If job is completed/failed, remove from storage
    else:
        del active_jobs[job_id]
        if job_id in job_results:
            del job_results[job_id]

        logger.info(f"Deleted job {job_id}")
        return {"message": f"Job {job_id} deleted successfully"}

@router.get("/health")
async def ingestion_health() -> dict[str, Any]:
    """Health check endpoint for ingestion service."""
    try:
        pipeline = MaterialIngestionPipeline()
        health = await pipeline.health_check()
        await pipeline.close()

        return {
            "service": "material_ingestion",
            "status": "healthy" if health.get("pipeline_healthy") else "unhealthy",
            "active_jobs": len([j for j in active_jobs.values() if j["status"] == "processing"]),
            "total_jobs": len(active_jobs),
            "components": health
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "material_ingestion",
            "status": "unhealthy",
            "error": str(e)
        }
