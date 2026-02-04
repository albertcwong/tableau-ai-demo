"""Salesforce JWT OAuth authenticator."""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import jwt
import httpx
from app.services.gateway.router import ProviderContext
from app.services.gateway.cache import token_cache
from app.core.config import settings

logger = logging.getLogger(__name__)


class SalesforceAuthenticator:
    """Authenticator for Salesforce JWT OAuth flow."""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        username: Optional[str] = None,
        token_url: str = "https://login.salesforce.com/services/oauth2/token"
    ):
        """Initialize Salesforce authenticator.
        
        Args:
            client_id: Salesforce Connected App client ID
            private_key_path: Path to private key PEM file
            username: Salesforce username (service account)
            token_url: OAuth token endpoint URL
        """
        self.client_id = client_id or settings.SALESFORCE_CLIENT_ID
        self.private_key_path = private_key_path or settings.SALESFORCE_PRIVATE_KEY_PATH
        self.username = username or settings.SALESFORCE_USERNAME
        self.token_url = token_url
        
        if not self.client_id:
            raise ValueError("SALESFORCE_CLIENT_ID is required")
        if not self.private_key_path:
            raise ValueError("SALESFORCE_PRIVATE_KEY_PATH is required")
        if not self.username:
            raise ValueError("SALESFORCE_USERNAME is required")
    
    def _load_private_key(self) -> str:
        """Load private key from file.
        
        Returns:
            Private key content as string
            
        Raises:
            FileNotFoundError: If key file doesn't exist
            ValueError: If key file is invalid
        """
        key_path = Path(self.private_key_path)
        
        if not key_path.exists():
            raise FileNotFoundError(f"Private key file not found: {self.private_key_path}")
        
        try:
            with open(key_path, 'r') as f:
                key_content = f.read()
            
            if not key_content.strip():
                raise ValueError(f"Private key file is empty: {self.private_key_path}")
            
            return key_content
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")
    
    def _generate_jwt(self) -> str:
        """Generate JWT assertion for Salesforce OAuth.
        
        Returns:
            Encoded JWT token string
        """
        private_key = self._load_private_key()
        
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=5)  # JWT expires in 5 minutes
        
        # JWT payload for Salesforce Connected App
        payload = {
            "iss": self.client_id,  # Issuer (Connected App client ID)
            "sub": self.username,    # Subject (username)
            "aud": self.token_url,  # Audience (token endpoint)
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
        }
        
        # Encode JWT using RS256 algorithm (Salesforce requires RS256)
        try:
            token = jwt.encode(
                payload,
                private_key,
                algorithm="RS256"
            )
            logger.debug("Generated Salesforce JWT assertion")
            return token
        except Exception as e:
            raise ValueError(f"Failed to generate JWT: {e}")
    
    async def _exchange_jwt_for_token(self, jwt_assertion: str) -> dict:
        """Exchange JWT assertion for OAuth access token.
        
        Args:
            jwt_assertion: JWT assertion string
            
        Returns:
            Token response dict with 'access_token' and 'expires_in'
            
        Raises:
            httpx.HTTPError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_assertion
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_token(self, auth_header: Optional[str] = None, context: Optional[ProviderContext] = None) -> str:
        """Get OAuth access token (from cache or new request).
        
        Args:
            auth_header: Not used for Salesforce (uses configured credentials)
            context: Provider context (optional, uses instance config if not provided)
            
        Returns:
            OAuth access token string
        """
        # Use context if provided, otherwise use instance config
        client_id = context.client_id if context else self.client_id
        identifier = client_id or self.client_id
        
        # Check cache first
        cached = token_cache.get("salesforce", identifier)
        if cached:
            logger.debug("Using cached Salesforce token")
            return cached["token"]
        
        # Generate new token
        logger.info("Generating new Salesforce OAuth token")
        jwt_assertion = self._generate_jwt()
        token_response = await self._exchange_jwt_for_token(jwt_assertion)
        
        access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", 3600)  # Default 1 hour
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # Cache token
        token_cache.set(
            provider="salesforce",
            identifier=identifier,
            token=access_token,
            expires_at=expires_at,
            metadata={
                "instance_url": token_response.get("instance_url"),
                "token_type": token_response.get("token_type", "Bearer")
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
        client_id = context.client_id if context else self.client_id
        identifier = client_id or self.client_id
        
        token_cache.delete("salesforce", identifier)
        return await self.get_token(auth_header, context)
