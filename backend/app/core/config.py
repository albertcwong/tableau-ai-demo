"""Application configuration."""
import os
from pathlib import Path
from pydantic import field_validator, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Union
from urllib.parse import urlparse

# Get the project root directory (2 levels up from this file: backend/app/core/config.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "Tableau AI Demo"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"  # Change in production!
    
    # CORS - stored as string in env, converted to list
    CORS_ORIGINS: str = "http://localhost:3000,https://localhost:3000,http://localhost:3001"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        if isinstance(self.CORS_ORIGINS, str):
            origins = [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]
            return origins if origins else ["http://localhost:3000", "https://localhost:3000", "http://localhost:3001"]
        elif isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return ["http://localhost:3000", "https://localhost:3000", "http://localhost:3001"]
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/tableau_demo"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TOKEN_TTL: int = 3600
    REDIS_POOL_SIZE: int = 10
    
    # Tableau
    TABLEAU_SERVER_URL: str = ""
    TABLEAU_PAT_ENCRYPTION_KEY: Optional[str] = None  # Base64-encoded Fernet key for PAT storage
    TABLEAU_SITE_ID: str = ""
    TABLEAU_CLIENT_ID: str = ""
    TABLEAU_CLIENT_SECRET: str = ""
    TABLEAU_SECRET_ID: Optional[str] = None  # Optional: Secret ID for JWT 'kid' header (defaults to client_id if not provided)
    TABLEAU_USERNAME: Optional[str] = None  # Optional: Username for JWT 'sub' claim (defaults to client_id)
    TABLEAU_API_VERSION: str = "3.21"  # Tableau REST API version (e.g., "3.21", "3.27")
    
    # Gateway (embedded in backend; uses BACKEND_API_URL)
    GATEWAY_ENABLED: bool = True
    MODEL_MAPPING: Optional[str] = None  # JSON string for custom model-to-provider mapping
    
    # SSL/TLS Configuration
    TABLEAU_VERIFY_SSL: bool = True  # Set to False to disable SSL verification for self-signed certs
    TABLEAU_SSL_CERT_PATH: Optional[str] = None  # Path to Tableau server's CA certificate file (.pem or .crt)
    
    # AI Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    
    # Salesforce
    SALESFORCE_CLIENT_ID: str = ""
    SALESFORCE_PRIVATE_KEY_PATH: str = "./credentials/salesforce-private-key.pem"
    SALESFORCE_USERNAME: str = ""
    SALESFORCE_MODELS_API_URL: str = "https://api.salesforce.com/einstein/platform/v1"
    
    # Vertex AI
    VERTEX_PROJECT_ID: str = ""
    VERTEX_LOCATION: str = "us-central1"
    VERTEX_SERVICE_ACCOUNT_PATH: str = "./credentials/vertex-sa.json"
    
    # Apple Endor
    APPLE_ENDOR_API_KEY: str = ""
    APPLE_ENDOR_ENDPOINT: str = ""
    
    # MCP Server
    MCP_SERVER_NAME: str = "tableau-ai-demo-mcp"
    MCP_TRANSPORT: str = "stdio"  # stdio or sse
    MCP_LOG_LEVEL: str = "info"
    
    # Auth0 Configuration (MVP)
    # Note: These are fallback values. Primary configuration is now in database (auth_configs table)
    # Admin can configure via /admin/auth-config endpoint
    AUTH0_DOMAIN: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_ISSUER: str = ""
    BACKEND_API_URL: str = "http://localhost:8000"  # Backend API URL for MCP Server
    TABLEAU_OAUTH_FRONTEND_REDIRECT: str = "http://localhost:3000"  # Frontend URL for OAuth callback redirect

    # EAS JWT: when Auth0 cannot set aud/sub (restricted claims), backend can construct the JWT.
    # Set path to RSA private key PEM. Tableau must register this backend as EAS (issuer=BACKEND_API_URL).
    EAS_JWT_KEY_PATH: Optional[str] = None
    # Override aud claim (default "tableau"). For site-level EAS: "tableau:<site_luid>"
    EAS_JWT_AUD: Optional[str] = None
    
    # VizQL Agent (DEPRECATED - use admin panel agent config instead)
    VIZQL_AGENT_TYPE: str = "tool_use"  # DEPRECATED: Use admin panel to configure agent versions. Fallback only.
    VIZQL_MAX_BUILD_RETRIES: int = 3  # DEPRECATED: Use admin panel to configure retry settings. Fallback only.
    VIZQL_MAX_EXECUTION_RETRIES: int = 3  # DEPRECATED: Use admin panel to configure retry settings. Fallback only.
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields from .env that aren't in this model
    )
    
    @field_validator('TABLEAU_SERVER_URL')
    @classmethod
    def validate_tableau_url(cls, v: str) -> str:
        """Validate Tableau server URL format."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('TABLEAU_SERVER_URL must start with http:// or https://')
        if v:
            try:
                urlparse(v)
            except Exception as e:
                raise ValueError(f'Invalid TABLEAU_SERVER_URL format: {e}')
        return v
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(('postgresql://', 'postgresql+psycopg2://', 'sqlite:///')):
            raise ValueError('DATABASE_URL must start with postgresql://, postgresql+psycopg2://, or sqlite:///')
        return v
    
    @field_validator('REDIS_URL')
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError('REDIS_URL must start with redis:// or rediss://')
        return v
    
    @field_validator('DB_POOL_SIZE', 'DB_MAX_OVERFLOW')
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Validate database pool size."""
        if v < 1:
            raise ValueError('Pool size must be at least 1')
        if v > 100:
            raise ValueError('Pool size should not exceed 100')
        return v
    
    @model_validator(mode='after')
    def warn_deprecated_vizql_config(self):
        """Warn about deprecated VizQL config env vars."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Check if deprecated vars are set (non-default values)
        if self.VIZQL_AGENT_TYPE != "tool_use":
            logger.warning(
                "VIZQL_AGENT_TYPE env var is deprecated. "
                "Please configure agent versions via the admin panel at /admin/agents. "
                "This env var is kept for backward compatibility only."
            )
        
        if self.VIZQL_MAX_BUILD_RETRIES != 3 or self.VIZQL_MAX_EXECUTION_RETRIES != 3:
            logger.warning(
                "VIZQL_MAX_BUILD_RETRIES and VIZQL_MAX_EXECUTION_RETRIES env vars are deprecated. "
                "Please configure retry settings via the admin panel at /admin/agents/vizql/settings. "
                "These env vars are kept for backward compatibility only."
            )
        
        return self


settings = Settings()

# Log configuration status (without exposing secrets)
if settings.DEBUG:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded .env from: {ENV_FILE}")
    logger.info(f"TABLEAU_SERVER_URL configured: {'Yes' if settings.TABLEAU_SERVER_URL else 'No'}")
    logger.info(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")
