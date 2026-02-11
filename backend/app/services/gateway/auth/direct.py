"""Direct API key passthrough authenticator."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.services.gateway.router import ProviderContext
from app.models.user import ProviderConfig

logger = logging.getLogger(__name__)


class DirectAuthenticator:
    """Authenticator for direct API key passthrough (OpenAI, Anthropic).
    
    Resolves API key from ProviderConfig per provider. No Authorization header from caller.
    """
    
    async def get_token(
        self,
        auth_header: Optional[str] = None,
        context: Optional[ProviderContext] = None,
        db: Optional[Session] = None
    ) -> str:
        """Get API key from ProviderConfig for the provider.
        
        Args:
            auth_header: Not used (kept for interface compatibility)
            context: Provider context (must have provider set)
            db: Database session (required for ProviderConfig lookup)
            
        Returns:
            API key string from ProviderConfig
            
        Raises:
            ValueError: If ProviderConfig not found or api_key missing
        """
        if not context or not context.provider:
            raise ValueError("Provider context required for direct authentication")
        
        if not db:
            raise ValueError("Database session required for ProviderConfig lookup")
        
        # Look up ProviderConfig for this provider
        provider_config = db.query(ProviderConfig).filter(
            ProviderConfig.provider_type == context.provider,
            ProviderConfig.is_active == True
        ).first()
        
        if not provider_config:
            raise ValueError(
                f"ProviderConfig not found for provider '{context.provider}'. "
                "Please configure the provider in Admin Console."
            )
        
        if not provider_config.api_key:
            raise ValueError(
                f"API key not configured for provider '{context.provider}'. "
                "Please set the API key in ProviderConfig."
            )
        
        logger.debug(f"Using API key from ProviderConfig for {context.provider}")
        return provider_config.api_key
    
    async def refresh_token(
        self,
        auth_header: Optional[str] = None,
        context: Optional[ProviderContext] = None,
        db: Optional[Session] = None
    ) -> str:
        """Refresh token (no-op for direct auth, just returns same token).
        
        Args:
            auth_header: Not used
            context: Provider context
            db: Database session
            
        Returns:
            Same API key from ProviderConfig
        """
        return await self.get_token(auth_header, context, db)
