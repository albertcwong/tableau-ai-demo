"""Authentication API endpoints."""
import logging
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import verify_password, create_access_token, decode_access_token, validate_auth0_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User, UserRole
from app.services.auth0_user_service import get_or_create_user_from_auth0
from app.services.auth_config_service import get_auth_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Create a reusable dependency for extracting the token
async def get_token_from_header(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User response model."""
    id: int
    username: str
    role: str
    is_active: bool
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    preferred_agent_type: Optional[str] = None
    tableau_username: Optional[str] = None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    Supports both Auth0 tokens (RS256) and internal tokens (HS256).
    """
    # Extract token from Authorization header
    authorization = request.headers.get("Authorization")
    if not authorization:
        logger.warning("No Authorization header provided in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning(f"Authorization header not in Bearer format: {authorization[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    logger.debug(f"Received token (length: {len(token)})")
    
    # Check auth config to see which methods are enabled
    auth_config = get_auth_config(db)
    
    # Try Auth0 token validation first (if OAuth is enabled)
    if auth_config.enable_oauth_auth and auth_config.auth0_domain and auth_config.auth0_audience:
        auth0_claims = validate_auth0_token(
            token,
            auth0_domain=auth_config.auth0_domain,
            auth0_audience=auth_config.auth0_audience,
            auth0_issuer=auth_config.auth0_issuer
        )
        if auth0_claims:
            logger.debug("Token validated as Auth0 token")
            # Get or create user from Auth0 claims
            try:
                user = get_or_create_user_from_auth0(db, auth0_claims)
                if not user.is_active:
                    logger.warning(f"Auth0 user is inactive: {user.username}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is inactive",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                logger.debug(f"Auth0 user authenticated: {user.username} (ID: {user.id})")
                return user
            except ValueError as e:
                logger.error(f"Error processing Auth0 user: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Auth0 token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    
    # Fall back to internal token validation (backward compatibility)
    payload = decode_access_token(token)
    if payload is None:
        logger.warning(f"Invalid token provided (failed to decode as Auth0 or internal token)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # JWT 'sub' claim is a string, convert to int
    user_id_str = payload.get("sub")
    if user_id_str is None:
        logger.warning(f"Token payload missing user ID: {payload}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid user ID format in token: {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"Looking up user with ID: {user_id}")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        logger.warning(f"User not found or inactive: user_id={user_id}, found={user is not None}, active={user.is_active if user else False}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"User authenticated successfully: {user.username} (ID: {user.id})")
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.post("/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint."""
    # First, try to find the user to check if they're an admin
    user = db.query(User).filter(User.username == login_data.username).first()
    
    # Check if password authentication is enabled (admins can always use password auth)
    auth_config = get_auth_config(db)
    is_admin = user and user.role == UserRole.ADMIN
    
    if not auth_config.enable_password_auth and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password authentication is disabled. Please use OAuth authentication."
        )
    
    if not user:
        logger.warning(f"Login attempt with non-existent username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        logger.warning(f"Login attempt with inactive user: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.password_hash:
        logger.warning(f"Login attempt for user without password (likely Auth0 user): {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not verify_password(login_data.password, user.password_hash):
        logger.warning(f"Invalid password for user: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create access token
    # Note: JWT 'sub' claim must be a string, so convert user.id to string
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role.value}
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "username": user.username,
            "role": user.role.value,
            "is_active": user.is_active
        }
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        is_active=current_user.is_active,
        preferred_provider=current_user.preferred_provider,
        preferred_model=current_user.preferred_model,
        preferred_agent_type=current_user.preferred_agent_type,
        tableau_username=current_user.tableau_username
    )


@router.post("/auth/logout")
async def logout():
    """Logout endpoint (client should discard token)."""
    return {"message": "Logged out successfully"}


class UserPreferencesUpdate(BaseModel):
    """User preferences update model."""
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    preferred_agent_type: Optional[str] = None


@router.put("/auth/preferences", response_model=UserResponse)
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's preferences (provider, model, agent type)."""
    if preferences.preferred_provider is not None:
        current_user.preferred_provider = preferences.preferred_provider
    if preferences.preferred_model is not None:
        current_user.preferred_model = preferences.preferred_model
    if preferences.preferred_agent_type is not None:
        current_user.preferred_agent_type = preferences.preferred_agent_type
    
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        is_active=current_user.is_active,
        preferred_provider=current_user.preferred_provider,
        preferred_model=current_user.preferred_model,
        preferred_agent_type=current_user.preferred_agent_type
    )


class AuthConfigPublicResponse(BaseModel):
    """Public auth configuration response (no sensitive data)."""
    enable_password_auth: bool
    enable_oauth_auth: bool


class AuthConfigPublicResponse(BaseModel):
    """Public auth configuration response (for login page)."""
    enable_password_auth: bool
    enable_oauth_auth: bool


class Auth0ConfigPublicResponse(BaseModel):
    """Public Auth0 configuration (for frontend SDK initialization)."""
    domain: Optional[str] = None
    client_id: Optional[str] = None
    audience: Optional[str] = None
    issuer: Optional[str] = None
    enabled: bool = False


@router.get("/auth/config", response_model=AuthConfigPublicResponse)
async def get_auth_config_public(db: Session = Depends(get_db)):
    """Get public authentication configuration (for login page)."""
    config = get_auth_config(db)
    return AuthConfigPublicResponse(
        enable_password_auth=config.enable_password_auth,
        enable_oauth_auth=config.enable_oauth_auth
    )


@router.get("/auth/auth0-config", response_model=Auth0ConfigPublicResponse)
async def get_auth0_config_public(db: Session = Depends(get_db)):
    """Get public Auth0 configuration for frontend SDK initialization."""
    config = get_auth_config(db)
    if not config.enable_oauth_auth:
        return Auth0ConfigPublicResponse(enabled=False)
    
    return Auth0ConfigPublicResponse(
        domain=config.auth0_domain,
        client_id=config.auth0_client_id,
        audience=config.auth0_audience,
        issuer=config.auth0_issuer,
        enabled=True
    )
