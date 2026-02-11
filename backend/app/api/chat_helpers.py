"""Helper functions for chat API - context preparation and message formatting."""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message, MessageRole, ChatContext
from app.services.memory import get_conversation_memory


def prepare_chat_context(db: Session, conversation_id: int) -> Dict[str, Any]:
    """
    Load conversation, context objects, and message history.
    Returns a dict with: conversation, context_objects, datasource_ids, view_ids,
    history_messages, messages (OpenAI format), context_summary.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        return {"conversation": None}

    context_objects = (
        db.query(ChatContext)
        .filter(ChatContext.conversation_id == conversation_id)
        .order_by(ChatContext.added_at)
        .all()
    )
    datasource_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == "datasource"]
    view_ids = [ctx.object_id for ctx in context_objects if ctx.object_type == "view"]

    history_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )
    conversation_memory = get_conversation_memory(conversation_id)
    context_summary = conversation_memory.get_context_summary()

    messages = [
        {
            "role": msg.role.value.lower() if isinstance(msg.role, MessageRole) else str(msg.role).lower(),
            "content": msg.content,
        }
        for msg in history_messages
    ]
    if len(history_messages) > 10 and context_summary:
        messages.insert(
            0,
            {"role": "system", "content": f"Conversation context: {context_summary}"},
        )

    return {
        "conversation": conversation,
        "context_objects": context_objects,
        "datasource_ids": datasource_ids,
        "view_ids": view_ids,
        "history_messages": history_messages,
        "messages": messages,
        "context_summary": context_summary,
    }


