"""MCP Tools for conversation management."""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.database import SessionLocal
from app.models.chat import Conversation, Message, MessageRole
from sqlalchemy import desc

logger = logging.getLogger(__name__)

# Import mcp from package __init__ to avoid circular import
try:
    from mcp_server import get_mcp
    mcp = get_mcp()
except ImportError:
    from mcp_server.server import mcp



def get_db_session():
    """Get database session (synchronous generator for use in async context)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp.tool()
async def chat_create_conversation(agent_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new conversation with personalized greeting based on agent type.
    
    Args:
        agent_type: Optional agent type ('general', 'vizql', or 'summary') for personalized greeting
    
    Returns:
        Dictionary with 'conversation_id' and 'created_at'
    """
    try:
        db = next(get_db_session())
        conversation = Conversation()
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Personalized greetings per agent type
        greeting_messages = {
            'general': "Hello! I'm your General Agent assistant. I can help you explore Tableau objects, answer questions about your data, and assist with general queries. What would you like to know?",
            'vizql': "Hello! I'm your VizQL Agent. I specialize in constructing and executing VizQL queries to interact with Tableau datasources. I can help you build queries, filter data, and explore your datasets. What would you like to query?",
            'summary': "Hello! I'm your Summary Agent. I excel at exporting and summarizing multiple Tableau views. I can help you combine insights from different visualizations and create comprehensive summaries. What views would you like me to summarize?",
        }
        
        # Default greeting if agent_type is not provided or invalid
        agent_type_normalized = agent_type.lower() if agent_type else 'general'
        greeting_content = greeting_messages.get(agent_type_normalized, greeting_messages['general'])
        
        # Create initial greeting message from assistant
        greeting_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=greeting_content,
            created_at=datetime.now(),
            extra_metadata={"is_greeting": True, "agent_type": agent_type_normalized}  # Mark as greeting message
        )
        db.add(greeting_message)
        db.commit()
        
        logger.info(f"Created conversation {conversation.id} with initial greeting for agent type: {agent_type_normalized}")
        return {
            "conversation_id": conversation.id,
            "created_at": conversation.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return {
            "error": str(e),
            "conversation_id": None,
        }


@mcp.tool()
async def chat_get_conversation(conversation_id: int) -> Dict[str, Any]:
    """
    Get a conversation by ID.
    
    Args:
        conversation_id: Conversation ID (required)
    
    Returns:
        Dictionary with conversation details
    """
    try:
        db = next(get_db_session())
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        
        if not conversation:
            return {
                "error": f"Conversation {conversation_id} not found",
                "conversation_id": conversation_id,
            }
        
        return {
            "conversation_id": conversation.id,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "message_count": len(conversation.messages),
        }
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return {
            "error": str(e),
            "conversation_id": conversation_id,
        }


@mcp.tool()
async def chat_list_conversations(
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List all conversations with pagination.
    
    Args:
        limit: Maximum number of conversations to return (default: 50)
        offset: Number of conversations to skip (default: 0)
    
    Returns:
        Dictionary with 'conversations' list and 'total' count
    """
    try:
        db = next(get_db_session())
        
        # Get total count
        total = db.query(Conversation).count()
        
        # Get paginated conversations
        conversations = db.query(Conversation).order_by(
            desc(Conversation.updated_at)
        ).offset(offset).limit(limit).all()
        
        return {
            "conversations": [
                {
                    "id": conv.id,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages),
                }
                for conv in conversations
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return {
            "error": str(e),
            "conversations": [],
            "total": 0,
        }


@mcp.tool()
async def chat_add_message(
    conversation_id: int,
    role: str,
    content: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a message to a conversation.
    
    Args:
        conversation_id: Conversation ID (required)
        role: Message role - 'user', 'assistant', or 'system' (required)
        content: Message content (required)
        model: Optional model name used for this message
    
    Returns:
        Dictionary with 'message_id' and message details
    """
    try:
        db = next(get_db_session())
        
        # Verify conversation exists
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return {
                "error": f"Conversation {conversation_id} not found",
                "message_id": None,
            }
        
        # Normalize role
        role_upper = role.upper()
        try:
            message_role = MessageRole(role_upper)
        except ValueError:
            return {
                "error": f"Invalid role '{role}'. Must be 'user', 'assistant', or 'system'",
                "message_id": None,
            }
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            role=message_role,
            content=content,
            model_used=model,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        logger.info(f"Added message {message.id} to conversation {conversation_id}")
        return {
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role.value,
            "content": message.content,
            "model_used": message.model_used,
            "created_at": message.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error adding message: {e}")
        return {
            "error": str(e),
            "message_id": None,
        }


@mcp.tool()
async def chat_get_messages(
    conversation_id: int,
    limit: Optional[int] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get messages for a conversation with pagination.
    
    Args:
        conversation_id: Conversation ID (required)
        limit: Maximum number of messages to return (default: all)
        offset: Number of messages to skip (default: 0)
    
    Returns:
        Dictionary with 'messages' list
    """
    try:
        db = next(get_db_session())
        
        # Verify conversation exists
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return {
                "error": f"Conversation {conversation_id} not found",
                "messages": [],
            }
        
        # Build query
        query = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at)
        
        # Apply pagination
        if limit:
            query = query.offset(offset).limit(limit)
        else:
            query = query.offset(offset)
        
        messages = query.all()
        
        return {
            "messages": [
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role).upper(),
                    "content": msg.content,
                    "model_used": msg.model_used,
                    "tokens_used": msg.tokens_used,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
            "conversation_id": conversation_id,
            "count": len(messages),
        }
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return {
            "error": str(e),
            "messages": [],
        }


@mcp.tool()
async def chat_send_message(
    conversation_id: int,
    content: str,
    model: str = "gpt-4",
    provider: str = "openai",
    agent_type: Optional[str] = None,
    stream: bool = False,
    auth0_token: Optional[str] = None,
    x_tableau_config_id: Optional[str] = None,
    x_tableau_auth_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a message to the chat API and get an AI response. Invokes the agent service via backend HTTP.
    Requires Auth0 token for authenticated requests. Pass auth0_token or set AUTH0_ACCESS_TOKEN env.

    Args:
        conversation_id: Conversation ID (required)
        content: Message content (required)
        model: AI model to use (default: gpt-4)
        provider: Provider name e.g. openai, apple, vertex (default: openai)
        agent_type: Optional - vizql, summary, or multi_agent
        stream: Whether to stream response (default: False)
        auth0_token: Auth0 access token (optional, falls back to env AUTH0_ACCESS_TOKEN)
        x_tableau_config_id: Tableau config ID for datasource/view context
        x_tableau_auth_type: Tableau auth type e.g. connected_app, pat

    Returns:
        Dictionary with message, conversation_id, model, tokens_used
    """
    try:
        from mcp_server.utils.backend_client import call_backend_api
        try:
            from mcp_server import get_auth0_token
            token = auth0_token or get_auth0_token()
        except ImportError:
            token = auth0_token

        if not token:
            return {
                "error": "Auth0 token required. Set AUTH0_ACCESS_TOKEN env or pass auth0_token.",
                "message": None,
            }

        payload = {
            "conversation_id": conversation_id,
            "content": content,
            "model": model,
            "provider": provider,
            "stream": stream,
        }
        if agent_type:
            payload["agent_type"] = agent_type

        extra = {}
        if x_tableau_config_id:
            extra["X-Tableau-Config-Id"] = x_tableau_config_id
        if x_tableau_auth_type:
            extra["X-Tableau-Auth-Type"] = x_tableau_auth_type

        result = await call_backend_api(
            endpoint="/api/v1/chat/message",
            method="POST",
            data=payload,
            auth0_token=token,
            extra_headers=extra if extra else None,
        )
        return result
    except Exception as e:
        logger.error(f"Error sending chat message: {e}", exc_info=True)
        return {"error": str(e), "message": None}
