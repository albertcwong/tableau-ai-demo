"""Redis-backed token store for PAT authentication."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.cache import redis_client
from app.services.tableau.token_store import TableauTokenStore, TokenEntry

logger = logging.getLogger(__name__)

# TTL: 7 minutes (slightly less than typical 8-minute token expiry)
PAT_TOKEN_TTL_SECONDS = 7 * 60


class TableauPATTokenStore:
    """Redis-backed token store for PAT authentication.
    
    PAT tokens must be shared across all workers to prevent multiple sign-ins
    that would invalidate each other.
    """
    
    def _key(self, user_id: int, config_id: int) -> str:
        """Generate Redis key for token."""
        return f"tableau:pat:{user_id}:{config_id}"
    
    def get(self, user_id: int, config_id: int, auth_type: str) -> Optional[TokenEntry]:
        """Get cached PAT token if valid."""
        if auth_type != "pat":
            return None
        
        try:
            key = self._key(user_id, config_id)
            data = redis_client.get(key)
            if not data:
                return None
            
            # Deserialize token entry
            entry_dict = json.loads(data)
            expires_at = datetime.fromisoformat(entry_dict["expires_at"])
            
            # Check if expired (with 1 minute buffer)
            if datetime.now(timezone.utc) >= (expires_at - timedelta(minutes=1)):
                redis_client.delete(key)
                return None
            
            return TokenEntry(
                token=entry_dict["token"],
                expires_at=expires_at,
                site_id=entry_dict.get("site_id"),
                site_content_url=entry_dict.get("site_content_url"),
            )
        except Exception as e:
            logger.error(f"Error getting PAT token from Redis: {e}")
            return None
    
    def set(self, user_id: int, config_id: int, auth_type: str, entry: TokenEntry) -> None:
        """Store PAT token in Redis."""
        if auth_type != "pat":
            return
        
        try:
            key = self._key(user_id, config_id)
            entry_dict = {
                "token": entry.token,
                "expires_at": entry.expires_at.isoformat(),
                "site_id": entry.site_id,
                "site_content_url": entry.site_content_url,
            }
            redis_client.setex(
                key,
                PAT_TOKEN_TTL_SECONDS,
                json.dumps(entry_dict)
            )
            logger.debug(f"Cached PAT token in Redis for user={user_id} config={config_id}")
        except Exception as e:
            logger.error(f"Error storing PAT token in Redis: {e}")
    
    def invalidate(self, user_id: int, config_id: int, auth_type: str) -> None:
        """Remove PAT token from Redis."""
        if auth_type != "pat":
            return
        
        try:
            key = self._key(user_id, config_id)
            redis_client.delete(key)
            logger.info(f"Invalidated PAT token in Redis for user={user_id} config={config_id}")
        except Exception as e:
            logger.error(f"Error invalidating PAT token in Redis: {e}")


# Singleton instance
pat_token_store = TableauPATTokenStore()
