"""Authentication configuration service with caching."""
import logging
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.user import AuthConfig
from app.core.config import settings
from app.core.database import get_db, safe_commit
from app.services.pat_encryption import decrypt_secret, encrypt_secret

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
        safe_commit(db)
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
    backend_api_url: Optional[str] = None,
    tableau_oauth_frontend_redirect: Optional[str] = None,
    eas_jwt_key_pem: Optional[str] = None,
    cors_origins: Optional[str] = None,
    mcp_server_name: Optional[str] = None,
    mcp_transport: Optional[str] = None,
    mcp_log_level: Optional[str] = None,
    redis_token_ttl: Optional[int] = None,
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
    if backend_api_url is not None:
        config.backend_api_url = (backend_api_url or "").strip() or None
    if tableau_oauth_frontend_redirect is not None:
        config.tableau_oauth_frontend_redirect = (tableau_oauth_frontend_redirect or "").strip() or None
    if eas_jwt_key_pem is not None:
        config.eas_jwt_key_pem_encrypted = encrypt_secret(eas_jwt_key_pem) if eas_jwt_key_pem.strip() else None
    if cors_origins is not None:
        config.cors_origins = (cors_origins or "").strip() or None
    if mcp_server_name is not None:
        config.mcp_server_name = (mcp_server_name or "").strip() or None
    if mcp_transport is not None:
        config.mcp_transport = (mcp_transport or "").strip() or None
    if mcp_log_level is not None:
        config.mcp_log_level = (mcp_log_level or "").strip() or None
    if redis_token_ttl is not None:
        config.redis_token_ttl = redis_token_ttl
    if updated_by is not None:
        config.updated_by = updated_by

    safe_commit(db)
    db.refresh(config)
    
    # Invalidate cache
    invalidate_auth_config_cache()
    
    logger.info(f"Auth config updated: password={config.enable_password_auth}, oauth={config.enable_oauth_auth}")
    return config


def get_resolved_backend_api_url(db: Session) -> str:
    """Backend API URL: DB overrides settings."""
    config = get_auth_config(db, use_cache=False)
    url = (config.backend_api_url or "").strip() if config else ""
    return url or (settings.BACKEND_API_URL or "http://localhost:8000")


def get_resolved_tableau_oauth_frontend_redirect(db: Session) -> str:
    """Frontend redirect URL: DB overrides settings."""
    config = get_auth_config(db, use_cache=False)
    url = (config.tableau_oauth_frontend_redirect or "").strip() if config else ""
    return url or (settings.TABLEAU_OAUTH_FRONTEND_REDIRECT or "http://localhost:3000")


def get_resolved_cors_origins(db: Session) -> List[str]:
    """CORS origins: DB overrides settings."""
    config = get_auth_config(db, use_cache=True)
    val = (config.cors_origins or "").strip() if config and config.cors_origins else ""
    if val:
        return [o.strip() for o in val.split(",") if o.strip()]
    raw = settings.CORS_ORIGINS or ""
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:3000", "https://localhost:3000", "http://localhost:3001"]


def get_resolved_gateway_enabled(db: Session) -> bool:
    """Gateway is always enabled (embedded in backend)."""
    return True


def get_resolved_mcp_server_name(db: Session) -> str:
    """MCP server name: DB overrides settings."""
    config = get_auth_config(db, use_cache=True)
    val = (config.mcp_server_name or "").strip() if config and config.mcp_server_name else ""
    return val or getattr(settings, "MCP_SERVER_NAME", "tableau-ai-demo-mcp")


def get_resolved_mcp_transport(db: Session) -> str:
    """MCP transport: DB overrides settings."""
    config = get_auth_config(db, use_cache=True)
    val = (config.mcp_transport or "").strip() if config and config.mcp_transport else ""
    return val or getattr(settings, "MCP_TRANSPORT", "stdio")


def get_resolved_mcp_log_level(db: Session) -> str:
    """MCP log level: DB overrides settings."""
    config = get_auth_config(db, use_cache=True)
    val = (config.mcp_log_level or "").strip() if config and config.mcp_log_level else ""
    return val or getattr(settings, "MCP_LOG_LEVEL", "info")


def get_resolved_redis_token_ttl(db: Session) -> int:
    """Redis token TTL: DB overrides settings."""
    config = get_auth_config(db, use_cache=True)
    if config and config.redis_token_ttl is not None:
        return config.redis_token_ttl
    return getattr(settings, "REDIS_TOKEN_TTL", 3600)


def get_resolved_eas_jwt_key_content(db: Session) -> Optional[str]:
    """EAS JWT key PEM content: from DB (decrypted) or from file. Never expose to API."""
    config = get_auth_config(db, use_cache=False)
    if config and config.eas_jwt_key_pem_encrypted:
        try:
            return decrypt_secret(config.eas_jwt_key_pem_encrypted)
        except Exception as e:
            logger.error("Failed to decrypt EAS JWT key from DB: %s", e)
            return None
    key_path = getattr(settings, "EAS_JWT_KEY_PATH", None)
    if key_path:
        path = Path(key_path)
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent / key_path
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error("Failed to read EAS JWT key from file: %s", e)
    return None
