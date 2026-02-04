"""Direct API key passthrough authenticator."""
import logging
from typing import Optional
from app.services.gateway.router import ProviderContext

logger = logging.getLogger(__name__)


class DirectAuthenticator:
    """Authenticator for direct API key passthrough (OpenAI, Anthropic)."""
    
    async def get_token(self, auth_header: Optional[str] = None, context: Optional[ProviderContext] = None) -> str:
        """Extract API key from Authorization header.
        
        Args:
            auth_header: Authorization header (e.g., "Bearer sk-...")
            context: Provider context (not used for direct auth)
            
        Returns:
            API key string
            
        Raises:
            ValueError: If auth_header is missing or invalid
        """
        if not auth_header:
            raise ValueError("Authorization header required for direct authentication")
        
        # Remove "Bearer " prefix if present
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header
        
        if not token:
            raise ValueError("API key not found in Authorization header")
        
        logger.debug("Using direct API key authentication")
        return token
    
    async def refresh_token(self, auth_header: Optional[str] = None, context: Optional[ProviderContext] = None) -> str:
        """Refresh token (no-op for direct auth, just returns same token).
        
        Args:
            auth_header: Authorization header
            context: Provider context
            
        Returns:
            Same API key
        """
        return await self.get_token(auth_header, context)
