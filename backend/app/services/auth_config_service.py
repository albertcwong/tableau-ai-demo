"""Authentication configuration service with caching."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import AuthConfig
from app.core.database import get_db

logger = logging.getLogger(__name__)

# In-memory cache for auth config (invalidated on update)
_auth_config_cache: Optional[AuthConfig] = None
_cache_timestamp: Optional[float] = None
CACHE_TTL_SECONDS = 60  # Cache for 60 seconds


def get_auth_config(db: Session, use_cache: bool = True) -> AuthConfig:
    """
    Get the current authentication configuration.
    Uses caching to avoid database queries on every request.
    
    Args:
        db: Database session
        use_cache: Whether to use cached value (default: True)
    
    Returns:
        AuthConfig: Current authentication configuration
    """
    global _auth_config_cache, _cache_timestamp
    import time
    
    # Check cache if enabled and valid
    if use_cache and _auth_config_cache is not None and _cache_timestamp is not None:
        age = time.time() - _cache_timestamp
        if age < CACHE_TTL_SECONDS:
            return _auth_config_cache
    
    # Fetch from database
    config = db.query(AuthConfig).order_by(AuthConfig.updated_at.desc()).first()
    
    if config is None:
        # Create default config if none exists
        logger.info("No auth config found, creating default (password auth enabled)")
        config = AuthConfig(
            enable_password_auth=True,
            enable_oauth_auth=False
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    # Update cache
    _auth_config_cache = config
    _cache_timestamp = time.time()
    
    return config


def invalidate_auth_config_cache():
    """Invalidate the auth config cache (call after updates)."""
    global _auth_config_cache, _cache_timestamp
    _auth_config_cache = None
    _cache_timestamp = None
    logger.debug("Auth config cache invalidated")


def update_auth_config(
    db: Session,
    enable_password_auth: Optional[bool] = None,
    enable_oauth_auth: Optional[bool] = None,
    auth0_domain: Optional[str] = None,
    auth0_client_id: Optional[str] = None,
    auth0_client_secret: Optional[str] = None,
    auth0_audience: Optional[str] = None,
    auth0_issuer: Optional[str] = None,
    auth0_tableau_metadata_field: Optional[str] = None,
    updated_by: Optional[int] = None
) -> AuthConfig:
    """
    Update authentication configuration.
    
    Args:
        db: Database session
        enable_password_auth: Enable password authentication
        enable_oauth_auth: Enable OAuth authentication
        auth0_domain: Auth0 domain
        auth0_audience: Auth0 audience
        auth0_issuer: Auth0 issuer
        updated_by: User ID who made the update
    
    Returns:
        AuthConfig: Updated configuration
    """
    config = get_auth_config(db, use_cache=False)
    
    if enable_password_auth is not None:
        config.enable_password_auth = enable_password_auth
    if enable_oauth_auth is not None:
        config.enable_oauth_auth = enable_oauth_auth
    if auth0_domain is not None:
        config.auth0_domain = auth0_domain
    if auth0_client_id is not None:
        config.auth0_client_id = auth0_client_id
    if auth0_client_secret is not None:
        config.auth0_client_secret = auth0_client_secret
    if auth0_audience is not None:
        config.auth0_audience = auth0_audience
    if auth0_issuer is not None:
        config.auth0_issuer = auth0_issuer
    if auth0_tableau_metadata_field is not None:
        config.auth0_tableau_metadata_field = auth0_tableau_metadata_field
    if updated_by is not None:
        config.updated_by = updated_by
    
    db.commit()
    db.refresh(config)
    
    # Invalidate cache
    invalidate_auth_config_cache()
    
    logger.info(f"Auth config updated: password={config.enable_password_auth}, oauth={config.enable_oauth_auth}")
    return config
