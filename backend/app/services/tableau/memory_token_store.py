"""In-memory token store adapter for Connected App and other auth types."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services.tableau.token_cache import get as get_cached_token, set as set_cached_token, invalidate as invalidate_cached_token
from app.services.tableau.token_store import TableauTokenStore, TokenEntry

logger = logging.getLogger(__name__)


class TableauMemoryTokenStore:
    """In-memory token store adapter for Connected App authentication.
    
    Uses the existing in-memory cache. Multiple tokens OK for Connected App.
    """
    
    def get(self, user_id: int, config_id: int, auth_type: str) -> Optional[TokenEntry]:
        """Get cached token from in-memory cache."""
        cached = get_cached_token(user_id, config_id, auth_type)
        if not cached:
            return None
        
        return TokenEntry(
            token=cached["token"],
            expires_at=cached["expires_at"],
            site_id=cached.get("site_id"),
            site_content_url=cached.get("site_content_url"),
        )
    
    def set(self, user_id: int, config_id: int, auth_type: str, entry: TokenEntry) -> None:
        """Store token in in-memory cache."""
        set_cached_token(
            user_id,
            config_id,
            auth_type,
            entry.token,
            entry.expires_at,
            entry.site_id,
            entry.site_content_url,
        )
    
    def invalidate(self, user_id: int, config_id: int, auth_type: str) -> None:
        """Remove token from in-memory cache."""
        invalidate_cached_token(user_id, config_id, auth_type)


# Singleton instance
memory_token_store = TableauMemoryTokenStore()
