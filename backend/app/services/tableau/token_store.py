"""Tableau token store abstraction for pluggable token storage."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class TokenEntry:
    """Token entry with metadata."""
    token: str
    expires_at: datetime
    site_id: Optional[str] = None
    site_content_url: Optional[str] = None


class TableauTokenStore(Protocol):
    """Protocol for Tableau token storage."""
    
    def get(self, user_id: int, config_id: int, auth_type: str) -> Optional[TokenEntry]:
        """Get cached token if valid."""
        ...
    
    def set(self, user_id: int, config_id: int, auth_type: str, entry: TokenEntry) -> None:
        """Store token."""
        ...
    
    def invalidate(self, user_id: int, config_id: int, auth_type: str) -> None:
        """Remove cached token."""
        ...
