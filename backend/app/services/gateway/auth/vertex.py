"""Vertex AI service account authenticator."""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from app.services.gateway.router import ProviderContext
from app.services.gateway.cache import token_cache
from app.core.config import settings

logger = logging.getLogger(__name__)

# Vertex AI OAuth token endpoint
VERTEX_TOKEN_URL = "https://oauth2.googleapis.com/token"
VERTEX_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class VertexAuthenticator:
    """Authenticator for Vertex AI service account flow."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        service_account_path: Optional[str] = None
    ):
        """Initialize Vertex AI authenticator.
        
        Args:
            project_id: GCP project ID
            location: GCP location/region (e.g., "us-central1")
            service_account_path: Path to service account JSON file
        """
        self.project_id = project_id or settings.VERTEX_PROJECT_ID
        self.location = location or settings.VERTEX_LOCATION
        self.service_account_path = service_account_path or settings.VERTEX_SERVICE_ACCOUNT_PATH
        
        if not self.project_id:
            raise ValueError("VERTEX_PROJECT_ID is required")
        if not self.service_account_path:
            raise ValueError("VERTEX_SERVICE_ACCOUNT_PATH is required")
    
    def _load_service_account(self) -> dict:
        """Load service account credentials from JSON file.
        
        Returns:
            Service account credentials dict
            
        Raises:
            FileNotFoundError: If credentials file doesn't exist
            ValueError: If credentials file is invalid
        """
        sa_path = Path(self.service_account_path)
        
        if not sa_path.exists():
            raise FileNotFoundError(f"Service account file not found: {self.service_account_path}")
        
        try:
            with open(sa_path, 'r') as f:
                credentials = json.load(f)
            
            # Validate required fields
            required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
            missing = [field for field in required_fields if field not in credentials]
            if missing:
                raise ValueError(f"Service account JSON missing required fields: {missing}")
            
            return credentials
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in service account file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load service account: {e}")
    
    def _create_service_account_credentials(self) -> service_account.Credentials:
        """Create Google service account credentials object.
        
        Returns:
            Service account credentials
        """
        sa_data = self._load_service_account()
        
        try:
            credentials = service_account.Credentials.from_service_account_info(
                sa_data,
                scopes=[VERTEX_SCOPE]
            )
            return credentials
        except Exception as e:
            raise ValueError(f"Failed to create service account credentials: {e}")
    
    async def _get_access_token(self, credentials: service_account.Credentials) -> dict:
        """Get OAuth access token from Google.
        
        Args:
            credentials: Service account credentials
            
        Returns:
            Token dict with 'token' and 'expiry'
        """
        # Refresh token if needed
        if not credentials.valid:
            credentials.refresh(Request())
        
        return {
            "token": credentials.token,
            "expiry": credentials.expiry
        }
    
    async def get_token(self, auth_header: Optional[str] = None, context: Optional[ProviderContext] = None) -> str:
        """Get OAuth access token (from cache or new request).
        
        Args:
            auth_header: Not used for Vertex AI (uses service account)
            context: Provider context (optional, uses instance config if not provided)
            
        Returns:
            OAuth access token string
        """
        # Use context if provided, otherwise use instance config
        project_id = context.project_id if context else self.project_id
        identifier = project_id or self.project_id
        
        # Check cache first
        cached = token_cache.get("vertex", identifier)
        if cached:
            logger.debug("Using cached Vertex AI token")
            return cached["token"]
        
        # Generate new token
        logger.info("Generating new Vertex AI OAuth token")
        credentials = self._create_service_account_credentials()
        token_data = await self._get_access_token(credentials)
        
        access_token = token_data["token"]
        expiry = token_data["expiry"]
        
        # Convert expiry datetime to UTC if needed
        if isinstance(expiry, datetime):
            expires_at = expiry
            if expiry.tzinfo is None:
                expires_at = expiry.replace(tzinfo=timezone.utc)
        else:
            # Fallback: assume 1 hour if expiry not provided
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Cache token
        token_cache.set(
            provider="vertex",
            identifier=identifier,
            token=access_token,
            expires_at=expires_at,
            metadata={
                "project_id": project_id,
                "location": context.location if context else self.location
            }
        )
        
        return access_token
    
    async def refresh_token(self, auth_header: Optional[str] = None, context: Optional[ProviderContext] = None) -> str:
        """Refresh OAuth token (forces new token generation).
        
        Args:
            auth_header: Not used
            context: Provider context
            
        Returns:
            New OAuth access token
        """
        # Clear cache and get new token
        project_id = context.project_id if context else self.project_id
        identifier = project_id or self.project_id
        
        token_cache.delete("vertex", identifier)
        return await self.get_token(auth_header, context)
