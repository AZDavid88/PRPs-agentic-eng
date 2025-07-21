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
    """Background task to process materials with LibrarianAgent integration."""
    try:
        # Update job status
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "status": "processing",
                "updated_at": datetime.now(),
                "message": "Initializing LibrarianAgent analysis..."
            })

        # LibrarianAgent pre-processing
        from src.agents.librarian import LibrarianAgent
        
        librarian = LibrarianAgent()
        
        # Update status for LibrarianAgent analysis
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "message": "LibrarianAgent analyzing materials for intelligent categorization..."
            })
        
        # Enhanced material analysis using LibrarianAgent
        enhanced_materials = []
        librarian_insights = []
        
        for i, material in enumerate(request.materials):
            try:
                # LibrarianAgent material analysis using proper model
                from src.models.librarian_models import MaterialAnalysisRequest
                
                analysis_request = MaterialAnalysisRequest(
                    materials=[material],
                    genre_context=request.genre_context or "unknown",
                    story_id=request.story_id or f"upload_{job_id}",
                    batch_size=1,
                    enable_cross_references=True,
                    complexity_level="medium"
                )
                
                # Get LibrarianAgent analysis
                analysis_result = await librarian.analyze_materials(analysis_request)
                
                # Extract insights for enhanced processing
                if analysis_result and hasattr(analysis_result, 'analysis_results'):
                    material_analysis = analysis_result.analysis_results[0] if analysis_result.analysis_results else None
                    if material_analysis:
                        librarian_insights.append({
                            "material_index": i,
                            "categories": material_analysis.primary_category,
                            "entities": material_analysis.extracted_entities,
                            "quality_score": material_analysis.quality_assessment.overall_score if hasattr(material_analysis, 'quality_assessment') else 0.8,
                            "cross_references": material_analysis.cross_references if hasattr(material_analysis, 'cross_references') else []
                        })
                        
                        # Enhanced material with LibrarianAgent metadata
                        enhanced_material = f"""[LIBRARIAN ANALYSIS]
Category: {material_analysis.primary_category}
Entities: {', '.join(material_analysis.extracted_entities[:5])}
Quality Score: {material_analysis.quality_assessment.overall_score if hasattr(material_analysis, 'quality_assessment') else 'N/A'}

[ORIGINAL CONTENT]
{material}"""
                        enhanced_materials.append(enhanced_material)
                    else:
                        enhanced_materials.append(material)
                        librarian_insights.append({"material_index": i, "analysis": "basic"})
                else:
                    enhanced_materials.append(material)
                    librarian_insights.append({"material_index": i, "analysis": "fallback"})
                    
            except Exception as e:
                logger.warning(f"LibrarianAgent analysis failed for material {i}: {e}")
                enhanced_materials.append(material)
                librarian_insights.append({"material_index": i, "analysis": "failed", "error": str(e)})
        
        # Update request with enhanced materials
        enhanced_request = MaterialIngestionRequest(
            materials=enhanced_materials,
            genre_context=request.genre_context,
            processing_mode=request.processing_mode,
            additional_genres=request.additional_genres,
            custom_categories=request.custom_categories,
            batch_size=request.batch_size,
            min_confidence_threshold=request.min_confidence_threshold,
            enable_cross_references=request.enable_cross_references,
            enable_progressive_disclosure=request.enable_progressive_disclosure,
            story_id=request.story_id,
            user_id=request.user_id
        )

        # Update status for main pipeline processing
        if job_id in active_jobs:
            active_jobs[job_id].update({
                "message": "Processing enhanced materials with pipeline..."
            })

        # Create progress callback
        progress_callback = progress_callback_factory(job_id)

        # Process materials with LibrarianAgent enhancements
        response = await pipeline.process_materials(enhanced_request, progress_callback)
        
        # Add LibrarianAgent insights to response using proper Pydantic fields
        response.librarian_insights = librarian_insights
        response.librarian_enhanced = True

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
        "librarian_analysis": {
            "enhanced": getattr(result, 'librarian_enhanced', False),
            "insights": getattr(result, 'librarian_insights', []),
            "analysis_count": len(getattr(result, 'librarian_insights', []))
        },
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

from pydantic import BaseModel

class GenreDetectionRequest(BaseModel):
    content: str

@router.post("/detect-genre")
async def detect_genre(request: GenreDetectionRequest) -> dict[str, Any]:
    """
    Detect genre from content using LibrarianAgent classification.
    
    Args:
        content: Text content to analyze for genre detection
        
    Returns:
        Suggested genres and confidence scores
    """
    try:
        from src.ingestion.classifier import MaterialClassifier
        
        if not request.content.strip():
            raise HTTPException(status_code=400, detail="Content cannot be empty")
        
        # Initialize classifier
        classifier = MaterialClassifier()
        
        # Use "unknown" as initial genre for detection
        result = await classifier.classify_single_material(
            material=request.content[:1500],  # Limit content for genre detection
            genre_context="unknown",
            additional_genres=None,
            custom_categories=None
        )
        
        # Extract genre suggestions from classification
        suggested_genres = []
        
        # Analyze content analysis for genre hints
        if hasattr(result, 'content_analysis') and result.content_analysis:
            themes = result.content_analysis.get('key_themes', [])
            narrative_elements = result.content_analysis.get('narrative_elements', [])
            
            # Map themes/elements to genres
            genre_mapping = {
                'litrpg': ['game', 'level', 'stats', 'rpg', 'system', 'quest', 'xp'],
                'fantasy': ['magic', 'dragon', 'wizard', 'spell', 'realm', 'sword'],
                'sci-fi': ['space', 'alien', 'technology', 'future', 'ship', 'planet'],
                'romance': ['love', 'relationship', 'heart', 'passion', 'marriage'],
                'mystery': ['detective', 'clue', 'murder', 'investigation', 'crime'],
                'horror': ['fear', 'death', 'monster', 'dark', 'scary', 'nightmare'],
                'historical': ['ancient', 'period', 'war', 'empire', 'historical'],
                'contemporary': ['modern', 'current', 'today', 'urban', 'realistic']
            }
            
            # Score genres based on theme/element matches
            genre_scores = {}
            all_text = ' '.join(themes + narrative_elements + [request.content]).lower()
            
            for genre, keywords in genre_mapping.items():
                score = sum(1 for keyword in keywords if keyword in all_text)
                if score > 0:
                    genre_scores[genre] = min(score / len(keywords), 1.0)
            
            # Sort by score and take top suggestions
            suggested_genres = [
                {"genre": genre, "confidence": score}
                for genre, score in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            ]
        
        # Add fallback suggestions if none detected
        if not suggested_genres:
            suggested_genres = [
                {"genre": "unknown", "confidence": 0.5},
                {"genre": "fantasy", "confidence": 0.3},
                {"genre": "contemporary", "confidence": 0.3}
            ]
        
        return {
            "detected_genres": suggested_genres,
            "primary_suggestion": suggested_genres[0]["genre"] if suggested_genres else "unknown",
            "analysis": {
                "content_length": len(request.content),
                "classification_confidence": result.confidence_score if hasattr(result, 'confidence_score') else 0.5,
                "detected_entities": result.extracted_entities if hasattr(result, 'extracted_entities') else []
            }
        }
        
    except Exception as e:
        logger.error(f"Genre detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Genre detection failed: {str(e)}")

@router.get("/available-genres")
async def get_available_genres() -> dict[str, Any]:
    """
    Get list of available genres for dynamic dropdown.
    
    Returns:
        List of supported genres with descriptions
    """
    genres = [
        {"value": "litrpg", "label": "LitRPG", "description": "Game-like progression systems"},
        {"value": "fantasy", "label": "Fantasy", "description": "Magic and mythical elements"},
        {"value": "sci-fi", "label": "Science Fiction", "description": "Futuristic and technological themes"},
        {"value": "romance", "label": "Romance", "description": "Love and relationship focused"},
        {"value": "mystery", "label": "Mystery", "description": "Investigation and puzzles"},
        {"value": "horror", "label": "Horror", "description": "Fear and supernatural elements"},
        {"value": "historical", "label": "Historical", "description": "Past time periods and events"},
        {"value": "contemporary", "label": "Contemporary", "description": "Modern day settings"},
        {"value": "gamelit", "label": "GameLit", "description": "Game world and mechanics"},
        {"value": "progression", "label": "Progression Fantasy", "description": "Power growth and advancement"},
        {"value": "unknown", "label": "Unknown/Other", "description": "Genre to be determined"}
    ]
    
    return {
        "genres": genres,
        "supports_dynamic_detection": True,
        "detection_endpoint": "/api/ingestion/detect-genre"
    }

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
