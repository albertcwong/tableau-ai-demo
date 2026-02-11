"""Apple Endor A3 token authenticator."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import httpx
from app.services.gateway.router import ProviderContext
from app.services.gateway.cache import token_cache
from app.models.user import ProviderConfig
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Default token expiration (A3 tokens typically expire in 1 hour, but we'll refresh earlier)
DEFAULT_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
TOKEN_BUFFER_SECONDS = 300  # 5 minute buffer before expiration


class EndorAuthenticator:
    """Authenticator for Apple Endor A3 token authentication."""
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_password: Optional[str] = None,
        other_app: Optional[int] = None,
        context: Optional[str] = None,
        one_time_token: bool = False,
        db: Optional[Session] = None
    ):
        """Initialize Endor authenticator.
        
        Args:
            app_id: Apple Endor App ID
            app_password: Apple Endor App Password
            other_app: otherApp parameter (default: 199323)
            context: Context parameter (default: "endor")
            one_time_token: Whether to use one-time tokens
            db: Optional database session to fetch config from
        """
        self.app_id = app_id
        self.app_password = app_password
        self.other_app = other_app or 199323
        self.context = context or "endor"
        self.one_time_token = one_time_token
        self.db = db
        self.idms_token_url = "https://idmsac.corp.apple.com/auth/apptoapp/token/generate"
    
    def _load_config_from_db(self, config_id: Optional[int] = None) -> bool:
        """Load configuration from database if not provided.
        
        Args:
            config_id: Optional config ID to load specific config
            
        Returns:
            True if config loaded successfully
        """
        if not self.db:
            return False
        
        try:
            query = self.db.query(ProviderConfig).filter(
                ProviderConfig.provider_type == "apple_endor",
                ProviderConfig.is_active == True
            )
            
            if config_id:
                query = query.filter(ProviderConfig.id == config_id)
            
            config = query.first()
            
            if not config:
                logger.warning("No active Endor provider config found in database")
                return False
            
            if not self.app_id:
                self.app_id = config.apple_endor_app_id
            if not self.app_password:
                self.app_password = config.apple_endor_app_password
            if config.apple_endor_other_app is not None:
                self.other_app = config.apple_endor_other_app
            if config.apple_endor_context:
                self.context = config.apple_endor_context
            if config.apple_endor_one_time_token is not None:
                self.one_time_token = config.apple_endor_one_time_token
            
            return True
        except Exception as e:
            logger.error(f"Error loading Endor config from database: {e}")
            return False
    
    async def _generate_a3_token(self) -> Dict[str, Any]:
        """Generate A3 token from Apple IDMS.
        
        Returns:
            Dict with 'token' and 'expires_in' (or 'expires_at')
            
        Raises:
            ValueError: If credentials are missing or token generation fails
            httpx.HTTPError: If HTTP request fails
        """
        # Try to load config from DB if not provided
        if not self.app_id or not self.app_password:
            if not self._load_config_from_db():
                raise ValueError("Apple Endor App ID and App Password are required")
        
        if not self.app_id:
            raise ValueError("Apple Endor App ID is required")
        if not self.app_password:
            raise ValueError("Apple Endor App Password is required")
        
        # Ensure string types for IDMS (handles int from DB)
        app_id_str = str(self.app_id).strip() if self.app_id else ""
        app_password_str = str(self.app_password).strip() if self.app_password else ""
        payload = {
            "appId": app_id_str,
            "appPassword": app_password_str,
            "otherApp": self.other_app,
            "context": self.context,
            "oneTimeToken": self.one_time_token
        }
        
        logger.info(f"Generating A3 token for App ID: {app_id_str[:10]}...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.idms_token_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            token_data = response.json()
            
            # IDMS may return "token" or "access_token"
            token = token_data.get("token") or token_data.get("access_token")
            if not token:
                raise ValueError(
                    f"A3 token not found in IDMS response. Keys: {list(token_data.keys())}"
                )
            
            logger.info("Successfully generated A3 token")
            
            # Calculate expiration (default to 1 hour if not provided)
            expires_in = token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            return {
                "token": token,
                "expires_in": expires_in,
                "expires_at": expires_at
            }
    
    async def get_token(
        self,
        auth_header: Optional[str] = None,
        context: Optional[ProviderContext] = None,
        optional_a3_token: Optional[str] = None
    ) -> str:
        """Get A3 token (from caller, cache, or new request).
        
        Args:
            auth_header: Not used for Endor (uses configured credentials)
            context: Provider context (may contain config_id or endpoint)
            optional_a3_token: Optional A3 token from frontend (e.g. for list models);
                if provided and valid, use it; otherwise generate from app_id+app_password
            
        Returns:
            A3 token string
        """
        # Use optional frontend-passed A3 token if provided
        if optional_a3_token and str(optional_a3_token).strip():
            logger.debug("Using optional A3 token from request")
            return str(optional_a3_token).strip()
        
        # Use config_id from context if available
        config_id = None
        if context and hasattr(context, 'config_id'):
            config_id = context.config_id
        
        # Try to load config from DB if not initialized
        if not self.app_id or not self.app_password:
            self._load_config_from_db(config_id)
        
        # Use app_id as cache identifier (ensure string)
        identifier = str(self.app_id) if self.app_id else "default"
        
        # Check cache first
        cached = token_cache.get("endor", identifier)
        if cached:
            logger.debug("Using cached Endor A3 token")
            return cached["token"]
        
        # Generate new token from app_id+app_password
        logger.info("Generating new Endor A3 token")
        token_data = await self._generate_a3_token()
        
        access_token = token_data["token"]
        expires_at = token_data["expires_at"]
        
        # Cache token
        token_cache.set(
            provider="endor",
            identifier=identifier,
            token=access_token,
            expires_at=expires_at,
            metadata={
                "app_id": self.app_id,
                "other_app": self.other_app,
                "context": self.context
            }
        )
        
        return access_token
    
    async def refresh_token(
        self,
        auth_header: Optional[str] = None,
        context: Optional[ProviderContext] = None
    ) -> str:
        """Refresh A3 token (forces new token generation).
        
        Args:
            auth_header: Not used
            context: Provider context
            
        Returns:
            New A3 token
        """
        # Clear cache and get new token
        identifier = str(self.app_id) if self.app_id else "default"
        token_cache.delete("endor", identifier)
        return await self.get_token(auth_header, context)
    
    def get_app_id(self) -> Optional[str]:
        """Get the App ID for header generation.
        
        Returns:
            App ID string
        """
        if not self.app_id:
            self._load_config_from_db()
        return str(self.app_id) if self.app_id else None
