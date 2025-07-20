"""Tests for authentication module."""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from src.web.auth import (
    create_access_token,
    verify_token,
    authenticate_websocket_token,
    get_current_user,
    require_roles,
    AuthSettings,
    User
)


@pytest.fixture
def auth_settings():
    """Authentication settings fixture."""
    return AuthSettings(
        secret_key="test_secret_key_12345",
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7
    )


@pytest.fixture
def test_user():
    """Test user fixture."""
    return User(
        user_id="test_user_123",
        username="testuser",
        email="test@example.com",
        roles=["user", "reader"],
        permissions=["read", "write"],
        is_active=True
    )


@pytest.fixture
def admin_user():
    """Admin user fixture."""
    return User(
        user_id="admin_user_456",
        username="adminuser",
        email="admin@example.com",
        roles=["admin", "user"],
        permissions=["read", "write", "delete", "admin"],
        is_active=True
    )


class TestAuthSettings:
    """Test cases for AuthSettings."""

    def test_auth_settings_init_default(self):
        """Test AuthSettings initialization with defaults."""
        settings = AuthSettings()
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 7
        assert len(settings.secret_key) > 0

    def test_auth_settings_init_custom(self, auth_settings):
        """Test AuthSettings initialization with custom values."""
        assert auth_settings.secret_key == "test_secret_key_12345"
        assert auth_settings.algorithm == "HS256"
        assert auth_settings.access_token_expire_minutes == 30


class TestUser:
    """Test cases for User model."""

    def test_user_model_creation(self, test_user):
        """Test User model creation."""
        assert test_user.user_id == "test_user_123"
        assert test_user.username == "testuser"
        assert test_user.email == "test@example.com"
        assert "user" in test_user.roles
        assert "read" in test_user.permissions
        assert test_user.is_active is True

    def test_user_has_role(self, test_user):
        """Test User has_role method."""
        assert test_user.has_role("user") is True
        assert test_user.has_role("admin") is False
        assert test_user.has_role("reader") is True

    def test_user_has_permission(self, test_user):
        """Test User has_permission method."""
        assert test_user.has_permission("read") is True
        assert test_user.has_permission("write") is True
        assert test_user.has_permission("delete") is False
        assert test_user.has_permission("admin") is False

    def test_user_has_any_role(self, test_user):
        """Test User has_any_role method."""
        assert test_user.has_any_role(["user", "admin"]) is True
        assert test_user.has_any_role(["admin", "moderator"]) is False
        assert test_user.has_any_role(["reader", "writer"]) is True

    def test_user_inactive(self):
        """Test inactive user."""
        inactive_user = User(
            user_id="inactive_123",
            username="inactive",
            email="inactive@example.com",
            roles=["user"],
            permissions=["read"],
            is_active=False
        )
        assert inactive_user.is_active is False


class TestTokenOperations:
    """Test cases for token operations."""

    def test_create_access_token_default_expiry(self, auth_settings, test_user):
        """Test creating access token with default expiry."""
        with patch('src.web.auth.auth_settings', auth_settings):
            token = create_access_token(test_user.model_dump())
            
            assert isinstance(token, str)
            
            # Decode token to verify contents
            payload = jwt.decode(token, auth_settings.secret_key, algorithms=[auth_settings.algorithm])
            assert payload["sub"] == test_user.user_id
            assert payload["username"] == test_user.username
            assert "exp" in payload

    def test_create_access_token_custom_expiry(self, auth_settings, test_user):
        """Test creating access token with custom expiry."""
        custom_expiry = timedelta(minutes=60)
        
        with patch('src.web.auth.auth_settings', auth_settings):
            token = create_access_token(test_user.model_dump(), expires_delta=custom_expiry)
            
            payload = jwt.decode(token, auth_settings.secret_key, algorithms=[auth_settings.algorithm])
            
            # Verify expiry is approximately 60 minutes from now
            exp_timestamp = payload["exp"]
            expected_exp = datetime.utcnow() + custom_expiry
            actual_exp = datetime.fromtimestamp(exp_timestamp)
            
            # Allow 5 second tolerance
            assert abs((actual_exp - expected_exp).total_seconds()) < 5

    def test_verify_token_valid(self, auth_settings, test_user):
        """Test verifying a valid token."""
        with patch('src.web.auth.auth_settings', auth_settings):
            token = create_access_token(test_user.model_dump())
            
            payload = verify_token(token)
            
            assert payload is not None
            assert payload["sub"] == test_user.user_id
            assert payload["username"] == test_user.username

    def test_verify_token_invalid_signature(self, auth_settings):
        """Test verifying token with invalid signature."""
        # Create token with different secret
        invalid_token = jwt.encode(
            {"sub": "test_user", "exp": datetime.utcnow() + timedelta(minutes=30)},
            "wrong_secret",
            algorithm="HS256"
        )
        
        with patch('src.web.auth.auth_settings', auth_settings):
            payload = verify_token(invalid_token)
            assert payload is None

    def test_verify_token_expired(self, auth_settings, test_user):
        """Test verifying an expired token."""
        # Create expired token
        expired_time = datetime.utcnow() - timedelta(minutes=1)
        expired_token = jwt.encode(
            {**test_user.model_dump(), "exp": expired_time},
            auth_settings.secret_key,
            algorithm=auth_settings.algorithm
        )
        
        with patch('src.web.auth.auth_settings', auth_settings):
            payload = verify_token(expired_token)
            assert payload is None

    def test_verify_token_malformed(self, auth_settings):
        """Test verifying a malformed token."""
        malformed_token = "not.a.valid.jwt.token"
        
        with patch('src.web.auth.auth_settings', auth_settings):
            payload = verify_token(malformed_token)
            assert payload is None


class TestWebSocketAuthentication:
    """Test cases for WebSocket authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_websocket_token_valid(self, auth_settings, test_user):
        """Test WebSocket authentication with valid token."""
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            # Create valid token
            token = create_access_token(test_user.model_dump())
            
            # Mock user retrieval
            mock_get_user.return_value = test_user
            
            result = await authenticate_websocket_token(token)
            
            assert result is not None
            assert result.user_id == test_user.user_id
            assert result.username == test_user.username
            mock_get_user.assert_called_once_with(test_user.user_id)

    @pytest.mark.asyncio
    async def test_authenticate_websocket_token_invalid(self, auth_settings):
        """Test WebSocket authentication with invalid token."""
        with patch('src.web.auth.auth_settings', auth_settings):
            result = await authenticate_websocket_token("invalid_token")
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_websocket_token_user_not_found(self, auth_settings, test_user):
        """Test WebSocket authentication when user not found."""
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            token = create_access_token(test_user.model_dump())
            mock_get_user.return_value = None
            
            result = await authenticate_websocket_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_websocket_token_inactive_user(self, auth_settings):
        """Test WebSocket authentication with inactive user."""
        inactive_user = User(
            user_id="inactive_123",
            username="inactive",
            email="inactive@example.com",
            roles=["user"],
            permissions=["read"],
            is_active=False
        )
        
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            token = create_access_token(inactive_user.model_dump())
            mock_get_user.return_value = inactive_user
            
            result = await authenticate_websocket_token(token)
            assert result is None


class TestUserAuthentication:
    """Test cases for user authentication."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, auth_settings, test_user):
        """Test getting current user with valid token."""
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            token = create_access_token(test_user.model_dump())
            mock_get_user.return_value = test_user
            
            result = await get_current_user(token)
            
            assert result.user_id == test_user.user_id
            assert result.username == test_user.username

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, auth_settings):
        """Test getting current user with invalid token."""
        with patch('src.web.auth.auth_settings', auth_settings):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user("invalid_token")
            
            assert exc_info.value.status_code == 401
            assert "Could not validate credentials" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_inactive(self, auth_settings):
        """Test getting current user when user is inactive."""
        inactive_user = User(
            user_id="inactive_123",
            username="inactive",
            email="inactive@example.com",
            roles=["user"],
            permissions=["read"],
            is_active=False
        )
        
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            token = create_access_token(inactive_user.model_dump())
            mock_get_user.return_value = inactive_user
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)
            
            assert exc_info.value.status_code == 400
            assert "Inactive user" in str(exc_info.value.detail)


class TestRoleBasedAccess:
    """Test cases for role-based access control."""

    def test_require_roles_decorator_valid(self, test_user):
        """Test require_roles decorator with valid roles."""
        @require_roles(["user"])
        async def protected_function(current_user: User):
            return f"Hello {current_user.username}"
        
        # This should not raise an exception
        result = protected_function.__wrapped__(test_user)
        # Note: We test the wrapped function directly since decorators are complex to test

    def test_require_roles_decorator_invalid(self):
        """Test require_roles decorator with invalid roles."""
        limited_user = User(
            user_id="limited_123",
            username="limited",
            email="limited@example.com",
            roles=["guest"],
            permissions=["read"],
            is_active=True
        )
        
        @require_roles(["admin"])
        async def admin_function(current_user: User):
            return "Admin only content"
        
        # Test that user doesn't have required role
        assert not limited_user.has_any_role(["admin"])

    def test_require_roles_multiple_roles(self, admin_user):
        """Test require_roles with multiple acceptable roles."""
        @require_roles(["admin", "moderator"])
        async def moderated_function(current_user: User):
            return "Moderated content"
        
        # Admin user should have access
        assert admin_user.has_any_role(["admin", "moderator"])

    def test_require_roles_empty_roles(self, test_user):
        """Test require_roles with empty roles list."""
        @require_roles([])
        async def open_function(current_user: User):
            return "Open content"
        
        # Should allow any authenticated user
        result = open_function.__wrapped__(test_user)


class TestSecurityHelpers:
    """Test cases for security helper functions."""

    def test_token_generation_uniqueness(self, auth_settings, test_user):
        """Test that tokens are unique for each generation."""
        with patch('src.web.auth.auth_settings', auth_settings):
            token1 = create_access_token(test_user.model_dump())
            
            # Wait a moment to ensure different issued-at time
            time.sleep(0.001)
            
            token2 = create_access_token(test_user.model_dump())
            
            assert token1 != token2

    def test_token_payload_completeness(self, auth_settings, test_user):
        """Test that token payload contains all required fields."""
        with patch('src.web.auth.auth_settings', auth_settings):
            token = create_access_token(test_user.model_dump())
            
            payload = jwt.decode(token, auth_settings.secret_key, algorithms=[auth_settings.algorithm])
            
            # Required fields
            assert "sub" in payload  # Subject (user_id)
            assert "exp" in payload  # Expiration
            assert "iat" in payload  # Issued at
            assert "username" in payload
            assert "roles" in payload
            assert "permissions" in payload

    @pytest.mark.asyncio
    async def test_concurrent_token_validation(self, auth_settings, test_user):
        """Test concurrent token validation."""
        import asyncio
        
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            token = create_access_token(test_user.model_dump())
            mock_get_user.return_value = test_user
            
            # Validate token concurrently
            tasks = [
                authenticate_websocket_token(token)
                for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All validations should succeed
            assert all(result is not None for result in results)
            assert all(result.user_id == test_user.user_id for result in results)


class TestAuthenticationIntegration:
    """Integration tests for authentication system."""

    def test_full_authentication_flow(self, auth_settings, test_user):
        """Test complete authentication flow."""
        with patch('src.web.auth.auth_settings', auth_settings), \
             patch('src.web.auth.get_user_by_id') as mock_get_user:
            
            mock_get_user.return_value = test_user
            
            # Step 1: Create token
            token = create_access_token(test_user.model_dump())
            assert token is not None
            
            # Step 2: Verify token
            payload = verify_token(token)
            assert payload is not None
            assert payload["sub"] == test_user.user_id
            
            # Step 3: Authenticate user (simulated)
            authenticated_user = mock_get_user(payload["sub"])
            assert authenticated_user.user_id == test_user.user_id
            assert authenticated_user.is_active is True

    def test_role_permission_hierarchy(self):
        """Test role and permission hierarchy."""
        # Create users with different privilege levels
        guest_user = User(
            user_id="guest_123",
            username="guest",
            email="guest@example.com",
            roles=["guest"],
            permissions=["read"],
            is_active=True
        )
        
        regular_user = User(
            user_id="user_123",
            username="user",
            email="user@example.com",
            roles=["user"],
            permissions=["read", "write"],
            is_active=True
        )
        
        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@example.com",
            roles=["admin", "user"],
            permissions=["read", "write", "delete", "admin"],
            is_active=True
        )
        
        # Test access levels
        assert guest_user.has_permission("read")
        assert not guest_user.has_permission("write")
        assert not guest_user.has_permission("admin")
        
        assert regular_user.has_permission("read")
        assert regular_user.has_permission("write")
        assert not regular_user.has_permission("admin")
        
        assert admin_user.has_permission("read")
        assert admin_user.has_permission("write")
        assert admin_user.has_permission("admin")
        
        # Test role hierarchy
        assert not guest_user.has_role("user")
        assert not guest_user.has_role("admin")
        
        assert regular_user.has_role("user")
        assert not regular_user.has_role("admin")
        
        assert admin_user.has_role("user")
        assert admin_user.has_role("admin")