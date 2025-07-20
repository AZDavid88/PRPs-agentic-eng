"""
Integration module to add WebSocket functionality to existing FastAPI app.

Extends the existing FastAPI application with WebSocket capabilities
without breaking current functionality.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.logger import get_logger
from src.web.websocket_routes import websocket_router
from src.web.auth import create_demo_token

logger = get_logger(__name__)

def setup_websocket_routes(app: FastAPI):
    """
    Add WebSocket routes to existing FastAPI application.
    
    Args:
        app: Existing FastAPI application instance
    """
    
    # Include WebSocket router
    app.include_router(
        websocket_router,
        tags=["WebSocket Communication"]
    )
    
    # Add demo token endpoint for testing
    @app.get("/api/auth/demo-token")
    async def get_demo_token(user_id: str = "demo_user"):
        """Get a demo JWT token for testing WebSocket connections."""
        try:
            token = create_demo_token(user_id)
            return {
                "token": token,
                "user_id": user_id,
                "expires_in": 1800,  # 30 minutes
                "websocket_url": "/ws/narrative"
            }
        except Exception as e:
            logger.error(f"Demo token creation failed: {e}")
            return {"error": "Token creation failed"}
    
    # Add WebSocket status endpoint
    @app.get("/api/websocket/status")
    async def websocket_status():
        """Get WebSocket service status and statistics."""
        try:
            from src.web.websocket_manager import connection_manager
            
            stats = connection_manager.get_stats()
            
            return {
                "websocket_service": "operational",
                "endpoints": {
                    "narrative": "/ws/narrative",
                    "dashboard": "/ws/dashboard"
                },
                "statistics": stats,
                "authentication": "JWT required",
                "demo_token_endpoint": "/api/auth/demo-token"
            }
            
        except Exception as e:
            logger.error(f"WebSocket status check failed: {e}")
            return {
                "websocket_service": "error",
                "error": str(e)
            }
    
    logger.info("WebSocket routes successfully integrated with FastAPI app")

def update_cors_for_websockets(app: FastAPI):
    """Update CORS configuration to support WebSocket connections."""
    
    # Find existing CORS middleware
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            # Update to include WebSocket origins
            existing_origins = middleware.kwargs.get("allow_origins", [])
            websocket_origins = [
                "ws://localhost:3000",
                "wss://localhost:3000", 
                "ws://localhost:8000",
                "wss://localhost:8000"
            ]
            
            # Combine existing and WebSocket origins
            all_origins = list(set(existing_origins + websocket_origins))
            middleware.kwargs["allow_origins"] = all_origins
            
            logger.info(f"Updated CORS for WebSocket support: {websocket_origins}")
            break
    else:
        logger.warning("No existing CORS middleware found - consider adding WebSocket CORS support")