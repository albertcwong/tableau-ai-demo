"""MCP Resources for conversations and Tableau data."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.chat import Conversation, Message, MessageRole
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)

# Import mcp from package __init__ to avoid circular import
try:
    from mcp_server import get_mcp
    mcp = get_mcp()
except ImportError:
    from mcp_server.server import mcp

# Cache for resources
_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, datetime] = {}
CACHE_TTL = timedelta(minutes=5)  # 5 minute TTL


def _is_cache_valid(key: str) -> bool:
    """Check if cache entry is still valid."""
    if key not in _cache or key not in _cache_timestamps:
        return False
    age = datetime.now() - _cache_timestamps[key]
    return age < CACHE_TTL


def _get_from_cache(key: str) -> Optional[Dict[str, Any]]:
    """Get value from cache if valid."""
    if _is_cache_valid(key):
        return _cache[key]
    return None


def _set_cache(key: str, value: Dict[str, Any]) -> None:
    """Set cache value with timestamp."""
    _cache[key] = value
    _cache_timestamps[key] = datetime.now()


@mcp.resource("conversation://{conversation_id}")
async def get_conversation_resource(conversation_id: str) -> str:
    """
    Get conversation history as a resource.
    
    URI format: conversation://{conversation_id}
    
    Args:
        conversation_id: Conversation ID from URI template
    
    Returns:
        JSON string with conversation messages
    """
    import json
    
    try:
        # Convert conversation_id to int
        conversation_id_int = int(conversation_id)
        
        # Check cache first
        cache_key = f"conversation:{conversation_id_int}"
        cached = _get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for conversation {conversation_id_int}")
            return json.dumps(cached)
        
        # Fetch from database
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id_int
            ).first()
            
            if not conversation:
                return json.dumps({
                    "error": f"Conversation {conversation_id_int} not found",
                    "conversation_id": conversation_id_int,
                })
            
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id_int
            ).order_by(Message.created_at).all()
            
            result = {
                "conversation_id": conversation.id,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role).upper(),
                        "content": msg.content,
                        "model_used": msg.model_used,
                        "created_at": msg.created_at.isoformat(),
                    }
                    for msg in messages
                ],
            }
            
            # Cache result
            _set_cache(cache_key, result)
            
            return json.dumps(result)
        finally:
            db.close()
    except ValueError as e:
        logger.error(f"Invalid conversation ID: {conversation_id}: {e}")
        return json.dumps({
            "error": f"Invalid conversation ID: {str(e)}",
        })
    except Exception as e:
        logger.error(f"Error fetching conversation resource: {e}")
        return json.dumps({
            "error": str(e),
        })


@mcp.resource("datasources://list")
async def get_datasources_list_resource() -> str:
    """
    Get cached list of datasources as a resource.
    
    URI format: datasources://list
    
    Returns:
        JSON string with datasources list
    """
    import json
    
    try:
        # Check cache first
        cache_key = "datasources:list"
        cached = _get_from_cache(cache_key)
        if cached:
            logger.debug("Cache hit for datasources list")
            return json.dumps(cached)
        
        # Fetch from Tableau
        client = TableauClient()
        result = await client.get_datasources()
        datasources = result["items"]
        
        result = {
            "datasources": datasources,
            "count": len(datasources),
            "cached_at": datetime.now().isoformat(),
        }
        
        # Cache result
        _set_cache(cache_key, result)
        
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching datasources resource: {e}")
        return json.dumps({
            "error": str(e),
            "datasources": [],
            "count": 0,
        })


@mcp.resource("views://list")
async def get_views_list_resource() -> str:
    """
    Get cached list of views as a resource.
    
    URI format: views://list
    
    Returns:
        JSON string with views list
    """
    import json
    
    try:
        # Check cache first
        cache_key = "views:list"
        cached = _get_from_cache(cache_key)
        if cached:
            logger.debug("Cache hit for views list")
            return json.dumps(cached)
        
        # Fetch from Tableau
        client = TableauClient()
        views = await client.get_views()
        
        result = {
            "views": views,
            "count": len(views),
            "cached_at": datetime.now().isoformat(),
        }
        
        # Cache result
        _set_cache(cache_key, result)
        
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching views resource: {e}")
        return json.dumps({
            "error": str(e),
            "views": [],
            "count": 0,
        })
