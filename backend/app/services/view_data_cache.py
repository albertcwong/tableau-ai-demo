"""View data cache service for Summary agent - caches view data per conversation."""
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CachedViewData:
    """Cached view data entry."""
    views_data: Dict[str, Any]
    views_metadata: Dict[str, Any]
    cached_at: datetime


# In-memory cache: key = (conversation_id, tuple(sorted(view_ids)))
_view_data_cache: Dict[Tuple[int, Tuple[str, ...]], CachedViewData] = {}

# Default TTL: 10 minutes
DEFAULT_TTL_MINUTES = 10


def get_cached(
    conversation_id: int,
    view_ids: list[str]
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Get cached view data for a conversation and views.
    
    Args:
        conversation_id: Conversation ID
        view_ids: List of view IDs
        
    Returns:
        Tuple of (views_data, views_metadata) if cache hit and not expired, else None
    """
    if not view_ids:
        return None
    
    key = (conversation_id, tuple(sorted(view_ids)))
    cached = _view_data_cache.get(key)
    
    if not cached:
        logger.debug(f"No cache entry for conversation {conversation_id}, views {view_ids}")
        return None
    
    # Check TTL
    age = datetime.now() - cached.cached_at
    if age > timedelta(minutes=DEFAULT_TTL_MINUTES):
        logger.debug(f"Cache entry expired for conversation {conversation_id}, views {view_ids} (age: {age})")
        del _view_data_cache[key]
        return None
    
    logger.info(f"Cache hit for conversation {conversation_id}, views {view_ids}")
    return (cached.views_data, cached.views_metadata)


def set_cached(
    conversation_id: int,
    view_ids: list[str],
    views_data: Dict[str, Any],
    views_metadata: Dict[str, Any]
) -> None:
    """
    Cache view data for a conversation and views.
    
    Args:
        conversation_id: Conversation ID
        view_ids: List of view IDs
        views_data: View data dict
        views_metadata: View metadata dict
    """
    if not view_ids:
        return
    
    key = (conversation_id, tuple(sorted(view_ids)))
    _view_data_cache[key] = CachedViewData(
        views_data=views_data,
        views_metadata=views_metadata,
        cached_at=datetime.now()
    )
    logger.info(f"Cached view data for conversation {conversation_id}, views {view_ids}")


def invalidate(
    conversation_id: int,
    view_ids: Optional[list[str]] = None
) -> None:
    """
    Invalidate cache entries for a conversation.
    
    Args:
        conversation_id: Conversation ID
        view_ids: Optional list of view IDs. If None, invalidates all entries for the conversation.
    """
    if view_ids:
        # Invalidate specific views
        key = (conversation_id, tuple(sorted(view_ids)))
        if key in _view_data_cache:
            del _view_data_cache[key]
            logger.info(f"Invalidated cache for conversation {conversation_id}, views {view_ids}")
    else:
        # Invalidate all entries for this conversation
        keys_to_remove = [k for k in _view_data_cache.keys() if k[0] == conversation_id]
        for key in keys_to_remove:
            del _view_data_cache[key]
        logger.info(f"Invalidated all cache entries for conversation {conversation_id} ({len(keys_to_remove)} entries)")


def clear_conversation(conversation_id: int) -> None:
    """Clear all cache entries for a conversation (alias for invalidate)."""
    invalidate(conversation_id)
