"""In-memory cache for Tableau auth tokens to avoid parallel sign-in invalidation.

When multiple requests (e.g. listDatasources + listWorkbooks) run in parallel,
each would sign in and invalidate the previous token. This cache ensures we
reuse a single token per (user_id, config_id, auth_type) and serialize sign-in.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache: (user_id, config_id, auth_type) -> {token, expires_at, site_id, site_content_url}
_cache: Dict[Tuple[int, int, str], dict] = {}
_locks: Dict[Tuple[int, int, str], asyncio.Lock] = {}


def _lock_for(user_id: int, config_id: int, auth_type: str) -> asyncio.Lock:
    key = (user_id, config_id, auth_type)
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def get(user_id: int, config_id: int, auth_type: str) -> Optional[dict]:
    """Get cached token if valid (not expired, not expiring within 1 min)."""
    key = (user_id, config_id, auth_type)
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at = entry.get("expires_at")
    if not expires_at:
        return None
    # Consider valid if at least 1 minute until expiry
    if datetime.now(timezone.utc) >= (expires_at - timedelta(minutes=1)):
        del _cache[key]
        return None
    return entry


def set(
    user_id: int,
    config_id: int,
    auth_type: str,
    token: str,
    expires_at: datetime,
    site_id: Optional[str] = None,
    site_content_url: Optional[str] = None,
) -> None:
    """Store token in cache."""
    key = (user_id, config_id, auth_type)
    _cache[key] = {
        "token": token,
        "expires_at": expires_at,
        "site_id": site_id,
        "site_content_url": site_content_url,
    }
    logger.debug(f"Cached Tableau token for user={user_id} config={config_id}")


def invalidate(user_id: int, config_id: int, auth_type: str) -> None:
    """Remove cached token (called on 401)."""
    key = (user_id, config_id, auth_type)
    if key in _cache:
        del _cache[key]
        logger.info(f"Invalidated Tableau token cache for user={user_id} config={config_id}")


@asynccontextmanager
async def with_lock(user_id: int, config_id: int, auth_type: str):
    """Async context manager for serializing sign-in per (user, config)."""
    lock = _lock_for(user_id, config_id, auth_type)
    async with lock:
        yield
