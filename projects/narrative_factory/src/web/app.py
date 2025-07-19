"""
FastAPI Web Application for Material Ingestion Pipeline.

Phase 3: Web Interface (Production)
Provides web interface for material upload, processing, and monitoring.
"""

from pathlib import Path
from typing import Any, AsyncGenerator, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.health import get_health_status
from src.logger import get_logger
from src.web.routes.ingestion import router as ingestion_router


logger = get_logger(__name__)

# Setup static files and templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

# Create directories if they don't exist
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management."""
    # Startup
    logger.info("🚀 Starting Narrative Factory Web Interface...")
    logger.info(f"📂 Static files: {static_dir}")
    logger.info(f"📄 Templates: {templates_dir}")
    logger.info("✅ Web interface ready for material ingestion")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Narrative Factory Web Interface...")

# Initialize FastAPI application
app = FastAPI(
    title="Narrative Factory - Material Ingestion",
    description="Web interface for processing and managing story materials",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS for development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React development server
        "http://localhost:8000",  # FastAPI development server
        "https://narrativefactory.ai",  # Production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(templates_dir))

# Include routers
app.include_router(
    ingestion_router,
    prefix="/api/ingestion",
    tags=["Material Ingestion"]
)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Serve the main application page."""
    try:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "Narrative Factory - Material Ingestion",
                "api_base": "/api"
            }
        )
    except Exception as e:
        logger.error(f"Error serving root page: {e}")
        # Fallback HTML response if template fails
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Narrative Factory - Material Ingestion</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .container { max-width: 800px; margin: 0 auto; }
                    .header { text-align: center; margin-bottom: 40px; }
                    .status { padding: 20px; background: #f5f5f5; border-radius: 8px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🏭 Narrative Factory</h1>
                        <h2>Material Ingestion Pipeline</h2>
                    </div>
                    <div class="status">
                        <p><strong>Status:</strong> Web interface is running</p>
                        <p><strong>API Docs:</strong> <a href="/api/docs">Swagger UI</a></p>
                        <p><strong>Redoc:</strong> <a href="/api/redoc">ReDoc</a></p>
                        <p><strong>Health Check:</strong> <a href="/health">System Health</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
        )

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        Dict containing system health status
    """
    try:
        # Get comprehensive health status from existing health module
        health_status = await get_health_status()

        # Add web-specific health checks
        web_health = {
            "web_server": {
                "status": "healthy",
                "fastapi_version": "0.104.0+",
                "static_files": static_dir.exists(),
                "templates": templates_dir.exists()
            }
        }

        # Combine with system health (handle different return types)
        combined_health: dict[str, Any]
        if isinstance(health_status, dict):
            combined_health = {**health_status, **web_health}
        else:
            # If health_status is not a dict, create a new dict
            combined_health = {
                "system_health": str(health_status),
                **web_health
            }

        return {
            "status": "healthy",
            "timestamp": combined_health.get("timestamp"),
            "components": combined_health,
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": "1.0.0"
        }

@app.get("/api/status")
async def api_status() -> Dict[str, Any]:
    """
    API status endpoint providing detailed system information.
    
    Returns:
        Dict containing API and system status
    """
    try:
        from src.ingestion.pipeline import MaterialIngestionPipeline
        from src.memory.service import MemoryService

        # Get pipeline health
        pipeline = MaterialIngestionPipeline()
        pipeline_health = await pipeline.health_check()

        # Get memory service health
        memory_service = MemoryService()
        # Note: Memory service doesn't have health_check method yet, so we'll test basic functionality
        try:
            await memory_service.initialize()
            memory_health = {"status": "healthy", "initialized": True}
            await memory_service.close()
        except Exception as e:
            memory_health = {"status": "unhealthy", "error": str(e)}

        return {
            "api_version": "1.0.0",
            "service": "material_ingestion_pipeline",
            "components": {
                "pipeline": pipeline_health,
                "memory_service": memory_health,
                "web_interface": {
                    "status": "healthy",
                    "endpoints": {
                        "upload": "/api/ingestion/upload",
                        "progress": "/api/ingestion/progress",
                        "status": "/api/ingestion/status",
                        "results": "/api/ingestion/results"
                    }
                }
            }
        }

    except Exception as e:
        logger.error(f"API status check failed: {e}")
        return {
            "api_version": "1.0.0",
            "service": "material_ingestion_pipeline",
            "status": "error",
            "error": str(e)
        }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Handle 404 errors with helpful information."""
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>404 - Page Not Found</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                .error { color: #e74c3c; }
                .links { margin-top: 20px; }
                .links a { margin: 0 10px; }
            </style>
        </head>
        <body>
            <h1 class="error">404 - Page Not Found</h1>
            <p>The requested page could not be found.</p>
            <div class="links">
                <a href="/">Home</a>
                <a href="/api/docs">API Docs</a>
                <a href="/health">Health Check</a>
            </div>
        </body>
        </html>
        """,
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> HTMLResponse:
    """Handle 500 errors with logging."""
    logger.error(f"Internal server error: {exc}")
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>500 - Internal Server Error</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                .error { color: #e74c3c; }
            </style>
        </head>
        <body>
            <h1 class="error">500 - Internal Server Error</h1>
            <p>Something went wrong on our end. Please try again later.</p>
            <p><a href="/">Return to Home</a></p>
        </body>
        </html>
        """,
        status_code=500
    )

if __name__ == "__main__":
    import uvicorn

    # Development server configuration
    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )