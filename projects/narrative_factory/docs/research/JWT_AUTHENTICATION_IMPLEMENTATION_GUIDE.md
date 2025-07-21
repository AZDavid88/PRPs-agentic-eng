# JWT Authentication Implementation Guide for Narrative Factory

**Research Date**: 2025-07-20  
**Context**: Missing `python-jose` dependency causing test failures in WebSocket HITL authentication  
**Goal**: Document JWT implementation patterns for real-time narrative interfaces  
**Source**: Context7 `/mpdavis/python-jose` library research + production patterns

---

## 🎯 **CRITICAL FINDINGS FOR NARRATIVE FACTORY**

### **Current Authentication Architecture**:
- **WebSocket HITL**: Real-time narrative generation interfaces
- **JWT Tokens**: User authentication for narrative sessions
- **Role-Based Access**: Different permissions for readers vs. collaborators
- **Session Management**: Long-running narrative generation sessions

### **Missing Dependencies Identified**:
- **`python-jose`**: JWT token creation and validation
- **Test Infrastructure**: Authentication testing patterns
- **Token Lifecycle**: Refresh and expiration handling

---

## 🔧 **JWT IMPLEMENTATION PATTERNS**

### **1. Basic JWT Token Management**

**Installation**:
```bash
uv add python-jose[cryptography]
```

**Core JWT Operations**:
```python
from jose import jwt, JWTError
from datetime import datetime, timedelta
import secrets

class JWTManager:
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    
    def create_access_token(self, data: dict) -> str:
        """Create access token for API/WebSocket authentication"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: dict) -> str:
        """Create refresh token for session persistence"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")
```

### **2. WebSocket Authentication Integration**

**WebSocket Connection Authentication**:
```python
from fastapi import WebSocket, HTTPException, status
from jose import JWTError

class WebSocketAuthenticator:
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
    
    async def authenticate_websocket(self, websocket: WebSocket, token: str) -> dict:
        """Authenticate WebSocket connection with JWT"""
        try:
            # Verify token
            payload = self.jwt_manager.verify_token(token)
            
            # Extract user information
            user_info = {
                "user_id": payload.get("sub"),
                "username": payload.get("username"),
                "roles": payload.get("roles", []),
                "narrative_permissions": payload.get("narrative_permissions", [])
            }
            
            return user_info
            
        except ValueError as e:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {e}"
            )
    
    def check_narrative_permission(self, user_info: dict, action: str, narrative_id: str) -> bool:
        """Check if user has permission for narrative action"""
        permissions = user_info.get("narrative_permissions", [])
        
        # Check role-based permissions
        if "admin" in user_info.get("roles", []):
            return True
        
        # Check narrative-specific permissions
        for perm in permissions:
            if (perm.get("narrative_id") == narrative_id and 
                action in perm.get("actions", [])):
                return True
        
        return False
```

### **3. Narrative Factory Specific Patterns**

**User Roles for Narrative Generation**:
```python
from enum import Enum

class NarrativeRole(str, Enum):
    READER = "reader"           # Can view narrative progress
    COLLABORATOR = "collaborator"  # Can provide input/feedback
    DIRECTOR = "director"       # Can control narrative direction
    ADMIN = "admin"            # Full access to all narratives

class NarrativePermission(BaseModel):
    narrative_id: str
    role: NarrativeRole
    actions: List[str]  # e.g., ["read", "comment", "direct", "approve"]
    expires_at: Optional[datetime] = None

def create_narrative_token(user_id: str, username: str, narrative_permissions: List[NarrativePermission]) -> str:
    """Create token with narrative-specific permissions"""
    token_data = {
        "sub": user_id,
        "username": username,
        "narrative_permissions": [perm.dict() for perm in narrative_permissions],
        "roles": ["collaborator"]  # Base role
    }
    
    return jwt_manager.create_access_token(token_data)
```

---

## 🔒 **SECURITY PATTERNS FOR LONG NARRATIVES**

### **Session Management for 1000+ Chapter Stories**:

**Long-Running Session Token**:
```python
class NarrativeSessionManager:
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
        self.active_sessions = {}  # In production: use Redis
    
    def create_narrative_session(self, user_id: str, narrative_id: str) -> dict:
        """Create authenticated session for long narrative"""
        session_id = secrets.token_urlsafe(16)
        
        # Create session token (longer expiry for narratives)
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "narrative_id": narrative_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Extended expiry for long narratives
        token = self.jwt_manager.create_access_token(session_data)
        
        # Store session info
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "narrative_id": narrative_id,
            "last_activity": datetime.utcnow(),
            "chapter_position": 1
        }
        
        return {
            "session_token": token,
            "session_id": session_id,
            "expires_in": self.jwt_manager.access_token_expire_minutes * 60
        }
    
    def validate_narrative_session(self, token: str, narrative_id: str) -> dict:
        """Validate session token for specific narrative"""
        try:
            payload = self.jwt_manager.verify_token(token)
            session_id = payload.get("session_id")
            
            # Check session exists and matches narrative
            if (session_id in self.active_sessions and 
                self.active_sessions[session_id]["narrative_id"] == narrative_id):
                
                # Update last activity
                self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
                return self.active_sessions[session_id]
            
            raise ValueError("Invalid session for narrative")
            
        except JWTError as e:
            raise ValueError(f"Session validation failed: {e}")
```

### **WebSocket Message Authentication**:

**Per-Message Validation**:
```python
class AuthenticatedWebSocketManager:
    def __init__(self, session_manager: NarrativeSessionManager):
        self.session_manager = session_manager
    
    async def handle_authenticated_message(self, websocket: WebSocket, message: dict):
        """Handle WebSocket message with authentication"""
        
        # Extract token from message
        token = message.get("auth_token")
        narrative_id = message.get("narrative_id")
        action = message.get("action")
        
        if not all([token, narrative_id, action]):
            await websocket.send_json({
                "error": "Missing authentication data",
                "code": "AUTH_REQUIRED"
            })
            return
        
        try:
            # Validate session
            session_info = self.session_manager.validate_narrative_session(token, narrative_id)
            
            # Check action permission
            if action in ["direct_narrative", "approve_chapter"]:
                # Require elevated permissions
                user_roles = session_info.get("roles", [])
                if "director" not in user_roles and "admin" not in user_roles:
                    await websocket.send_json({
                        "error": "Insufficient permissions",
                        "code": "PERMISSION_DENIED"
                    })
                    return
            
            # Process authenticated message
            await self.process_narrative_message(websocket, message, session_info)
            
        except ValueError as e:
            await websocket.send_json({
                "error": str(e),
                "code": "AUTH_FAILED"
            })
```

---

## 🧪 **TESTING PATTERNS**

### **JWT Authentication Tests**:

**Test Setup**:
```python
import pytest
from unittest.mock import Mock
from jose import jwt

@pytest.fixture
def jwt_manager():
    return JWTManager(secret_key="test-secret-key")

@pytest.fixture
def sample_user_data():
    return {
        "sub": "user123",
        "username": "test_user",
        "roles": ["collaborator"],
        "narrative_permissions": [
            {
                "narrative_id": "story1",
                "role": "collaborator",
                "actions": ["read", "comment"]
            }
        ]
    }

def test_create_and_verify_token(jwt_manager, sample_user_data):
    """Test JWT token creation and verification"""
    # Create token
    token = jwt_manager.create_access_token(sample_user_data)
    assert isinstance(token, str)
    
    # Verify token
    payload = jwt_manager.verify_token(token)
    assert payload["sub"] == "user123"
    assert payload["username"] == "test_user"

def test_invalid_token_handling(jwt_manager):
    """Test handling of invalid tokens"""
    with pytest.raises(ValueError, match="Invalid token"):
        jwt_manager.verify_token("invalid.token.here")

def test_expired_token_handling(jwt_manager, sample_user_data):
    """Test handling of expired tokens"""
    # Create token with past expiry
    import datetime
    past_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    
    expired_data = sample_user_data.copy()
    expired_data["exp"] = past_time.timestamp()
    
    expired_token = jwt.encode(expired_data, jwt_manager.secret_key, algorithm=jwt_manager.algorithm)
    
    with pytest.raises(ValueError, match="Invalid token"):
        jwt_manager.verify_token(expired_token)
```

### **WebSocket Authentication Tests**:

**WebSocket Test Patterns**:
```python
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket

def test_websocket_authentication_success(jwt_manager, sample_user_data):
    """Test successful WebSocket authentication"""
    
    # Create valid token
    token = jwt_manager.create_access_token(sample_user_data)
    
    # Mock WebSocket
    mock_websocket = Mock(spec=WebSocket)
    
    # Test authentication
    authenticator = WebSocketAuthenticator(jwt_manager)
    user_info = asyncio.run(authenticator.authenticate_websocket(mock_websocket, token))
    
    assert user_info["user_id"] == "user123"
    assert user_info["username"] == "test_user"

def test_websocket_authentication_failure(jwt_manager):
    """Test WebSocket authentication with invalid token"""
    
    mock_websocket = Mock(spec=WebSocket)
    authenticator = WebSocketAuthenticator(jwt_manager)
    
    with pytest.raises(HTTPException):
        asyncio.run(authenticator.authenticate_websocket(mock_websocket, "invalid.token"))
```

---

## 📋 **IMPLEMENTATION CHECKLIST**

### **Phase 1: Basic JWT Integration**
- [ ] Install `python-jose[cryptography]` dependency
- [ ] Create `JWTManager` class in `src/web/auth.py`
- [ ] Update WebSocket manager to use JWT authentication
- [ ] Add JWT configuration to main config

### **Phase 2: Narrative-Specific Features**
- [ ] Implement `NarrativeSessionManager` for long-running stories
- [ ] Add role-based permissions for narrative actions
- [ ] Create narrative-specific token generation
- [ ] Implement session persistence (Redis integration)

### **Phase 3: Testing & Security**
- [ ] Add comprehensive JWT test suite
- [ ] Implement WebSocket authentication tests
- [ ] Add security headers and CORS configuration
- [ ] Performance test with concurrent authenticated sessions

### **Phase 4: Production Features**
- [ ] Token refresh mechanism for long narratives
- [ ] Rate limiting per authenticated user
- [ ] Audit logging for narrative access
- [ ] Session cleanup and monitoring

---

## 🚀 **INTEGRATION WITH NARRATIVE FACTORY**

### **WebSocket HITL Authentication Flow**:
1. **User Login**: Generate JWT with narrative permissions
2. **WebSocket Connect**: Authenticate connection with token
3. **Message Validation**: Validate each narrative action
4. **Session Management**: Maintain long-running narrative sessions
5. **Permission Checking**: Verify actions against user roles

### **1000+ Chapter Considerations**:
- **Extended Sessions**: Longer token expiry for epic narratives
- **Chapter-Level Permissions**: Fine-grained access control
- **Progress Tracking**: Authenticated reading position
- **Collaborative Features**: Multi-user narrative development

---

**This JWT implementation will provide secure, scalable authentication for the Narrative Factory's real-time collaborative storytelling features while supporting the long-term nature of 1000+ chapter narratives.**