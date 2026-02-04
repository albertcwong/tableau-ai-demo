"""Token caching for OAuth tokens with TTL buffer."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.cache import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

# 5-minute buffer before token expiration
TOKEN_BUFFER_MINUTES = 5


class TokenCache:
    """Redis-based token cache with expiration buffer."""
    
    def __init__(self, redis_client_instance=None):
        """Initialize token cache.
        
        Args:
            redis_client_instance: Optional Redis client (defaults to global)
        """
        self.redis = redis_client_instance or redis_client
        self.buffer_minutes = TOKEN_BUFFER_MINUTES
        self.default_ttl = settings.REDIS_TOKEN_TTL
    
    def _make_key(self, provider: str, identifier: str) -> str:
        """Generate cache key for token.
        
        Args:
            provider: Provider name (e.g., "salesforce", "vertex")
            identifier: Unique identifier (e.g., client_id, project_id)
            
        Returns:
            Cache key string
        """
        return f"token:{provider}:{identifier}"
    
    def get(self, provider: str, identifier: str) -> Optional[Dict[str, Any]]:
        """Get cached token.
        
        Args:
            provider: Provider name
            identifier: Unique identifier
            
        Returns:
            Token dict with 'token' and 'expires_at' keys, or None if not found/expired
        """
        try:
            key = self._make_key(provider, identifier)
            cached_data = self.redis.get(key)
            
            if not cached_data:
                return None
            
            # Deserialize JSON
            data = json.loads(cached_data)
            
            # Check expiration (with buffer)
            expires_at_str = data.get("expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                buffer_time = expires_at - timedelta(minutes=self.buffer_minutes)
                
                if datetime.now(timezone.utc) >= buffer_time:
                    # Token expired or within buffer window
                    logger.debug(f"Token expired or within buffer: {provider}:{identifier}")
                    self.redis.delete(key)
                    return None
            
            return data
        except Exception as e:
            logger.warning(f"Error getting cached token for {provider}:{identifier}: {e}")
            return None
    
    def set(
        self,
        provider: str,
        identifier: str,
        token: str,
        expires_in_seconds: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Cache token with expiration.
        
        Args:
            provider: Provider name
            identifier: Unique identifier
            token: OAuth token string
            expires_in_seconds: Token TTL in seconds (if expires_at not provided)
            expires_at: Token expiration datetime (preferred)
            metadata: Optional additional metadata to store
            
        Returns:
            True if cached successfully
        """
        try:
            key = self._make_key(provider, identifier)
            
            # Calculate expiration
            if expires_at:
                expires_at_utc = expires_at
            elif expires_in_seconds:
                expires_at_utc = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
            else:
                # Default to configured TTL
                expires_at_utc = datetime.now(timezone.utc) + timedelta(seconds=self.default_ttl)
            
            # Store with buffer - cache expires 5 minutes before token expires
            cache_expires_at = expires_at_utc - timedelta(minutes=self.buffer_minutes)
            ttl_seconds = max(0, int((cache_expires_at - datetime.now(timezone.utc)).total_seconds()))
            
            # Prepare data
            data = {
                "token": token,
                "expires_at": expires_at_utc.isoformat(),
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            if metadata:
                data.update(metadata)
            
            # Store in Redis
            self.redis.setex(key, ttl_seconds, json.dumps(data))
            logger.debug(f"Cached token for {provider}:{identifier}, expires at {expires_at_utc}")
            return True
        except Exception as e:
            logger.error(f"Error caching token for {provider}:{identifier}: {e}")
            return False
    
    def delete(self, provider: str, identifier: str) -> bool:
        """Delete cached token.
        
        Args:
            provider: Provider name
            identifier: Unique identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            key = self._make_key(provider, identifier)
            self.redis.delete(key)
            logger.debug(f"Deleted cached token for {provider}:{identifier}")
            return True
        except Exception as e:
            logger.warning(f"Error deleting cached token for {provider}:{identifier}: {e}")
            return False
    
    def clear_provider(self, provider: str) -> int:
        """Clear all tokens for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Number of keys deleted
        """
        try:
            pattern = self._make_key(provider, "*")
            keys = list(self.redis.scan_iter(match=pattern))
            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} cached tokens for provider: {provider}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Error clearing tokens for provider {provider}: {e}")
            return 0


# Global token cache instance
token_cache = TokenCache()
