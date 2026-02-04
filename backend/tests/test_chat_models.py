"""Tests for chat history models."""
from datetime import datetime
from app.models.chat import Conversation, Message, Session


def test_create_conversation(db_session):
    """Test creating a conversation."""
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    assert conv.id is not None
    assert conv.created_at is not None
    assert conv.updated_at is not None


def test_message_conversation_relationship(db_session):
    """Test message-conversation relationship."""
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg = Message(conversation_id=conv.id, role="user", content="test message")
    db_session.add(msg)
    db_session.commit()
    
    assert msg.conversation.id == conv.id
    assert len(conv.messages) == 1
    assert conv.messages[0].content == "test message"


def test_message_ordering(db_session):
    """Test message ordering by created_at."""
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    # Create messages with explicit timestamps
    msg1 = Message(
        conversation=conv,
        role="user",
        content="first message",
        created_at=datetime(2024, 1, 1, 12, 0, 0)
    )
    msg2 = Message(
        conversation=conv,
        role="assistant",
        content="second message",
        created_at=datetime(2024, 1, 1, 12, 1, 0)
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    # Refresh to get ordered messages
    db_session.refresh(conv)
    messages = conv.messages
    
    assert len(messages) == 2
    assert messages[0].content == "first message"
    assert messages[1].content == "second message"


def test_message_model_used(db_session):
    """Test storing model used in message."""
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="AI response",
        model_used="gpt-4"
    )
    db_session.add(msg)
    db_session.commit()
    
    assert msg.model_used == "gpt-4"


def test_conversation_cascade_delete(db_session):
    """Test that deleting conversation deletes messages."""
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg1 = Message(conversation_id=conv.id, role="user", content="message 1")
    msg2 = Message(conversation_id=conv.id, role="assistant", content="message 2")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    conv_id = conv.id
    db_session.delete(conv)
    db_session.commit()
    
    # Verify messages are deleted
    remaining_messages = db_session.query(Message).filter_by(conversation_id=conv_id).all()
    assert len(remaining_messages) == 0


def test_create_session(db_session):
    """Test creating a session."""
    session = Session(user_id="user-123")
    db_session.add(session)
    db_session.commit()
    
    assert session.id is not None
    assert session.user_id == "user-123"
    assert session.created_at is not None
    assert session.last_active is not None


def test_session_last_active_update(db_session):
    """Test that last_active updates on modification."""
    session = Session(user_id="user-123")
    db_session.add(session)
    db_session.commit()
    
    original_active = session.last_active
    
    # Update session
    session.user_id = "user-456"
    db_session.commit()
    
    # last_active should be updated
    assert session.last_active > original_active
