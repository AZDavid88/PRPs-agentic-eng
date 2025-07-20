"""
WebSocket Authentication for Narrative Factory.

Provides JWT-based authentication for WebSocket connections with proper
security validation and user management.
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from pydantic import BaseModel

from src.logger import get_logger

logger = get_logger(__name__)

# JWT Configuration
SECRET_KEY = "narrative-factory-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: str
    role: str
    permissions: list[str] = []
    exp: datetime

class AuthenticationError(Exception):
    """Custom authentication error."""
    pass

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def authenticate_websocket(token: str) -> str:
    """
    Verify JWT token for WebSocket connections.
    
    Args:
        token: JWT token string
        
    Returns:
        str: User ID if token is valid
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        if not token or token.strip() == "":
            raise AuthenticationError("Token is required")
        
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Decode and validate token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Validate token expiration
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise AuthenticationError("Token has expired")
        
        logger.debug(f"WebSocket authentication successful for user: {user_id}")
        return user_id
        
    except jwt.ExpiredSignatureError:
        logger.warning("WebSocket authentication failed: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError as e:
        logger.warning(f"WebSocket authentication failed: invalid token - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except AuthenticationError as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

def get_user_permissions(user_id: str) -> list[str]:
    """Get user permissions for authorization."""
    # For now, return basic permissions
    # In production, this would query a user database
    default_permissions = ["read_agents", "read_workflows"]
    
    # Admin users get additional permissions
    if user_id.endswith("_admin"):
        default_permissions.extend(["write_agents", "write_workflows", "system_admin"])
    
    return default_permissions

def check_permission(user_id: str, required_permission: str) -> bool:
    """Check if user has required permission."""
    user_permissions = get_user_permissions(user_id)
    return required_permission in user_permissions

# Demo token creation for testing
def create_demo_token(user_id: str = "demo_user", role: str = "user") -> str:
    """Create a demo token for testing purposes."""
    token_data = {
        "sub": user_id,
        "role": role,
        "permissions": get_user_permissions(user_id)
    }
    return create_access_token(token_data)

# Alias for backward compatibility
verify_websocket_token = authenticate_websocket