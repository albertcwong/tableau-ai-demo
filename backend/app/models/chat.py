"""Chat history models."""
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Index, Enum as SQLEnum, JSON, BigInteger, TypeDecorator
from sqlalchemy.orm import relationship
from app.core.database import Base


class MessageRole(str, enum.Enum):
    """Message role enumeration."""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageRoleType(TypeDecorator):
    """Custom type decorator to handle enum values - accepts uppercase."""
    impl = SQLEnum(MessageRole, name="message_role", native_enum=True, create_constraint=True)
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Convert enum to uppercase string when binding to database."""
        if value is None:
            return None
        if isinstance(value, MessageRole):
            # Return the enum value which is now uppercase
            return value.value
        if isinstance(value, str):
            # Normalize to uppercase
            return value.upper()
        return str(value).upper()
    
    def process_result_value(self, value, dialect):
        """Convert database value back to enum when loading."""
        if value is None:
            return None
        if isinstance(value, MessageRole):
            return value
        # Convert string to enum - handle both uppercase and lowercase
        if isinstance(value, str):
            upper_value = value.upper()
            try:
                return MessageRole(upper_value)
            except ValueError:
                # Try mapping lowercase to uppercase
                lower_mapping = {'user': MessageRole.USER, 'assistant': MessageRole.ASSISTANT, 'system': MessageRole.SYSTEM}
                if value.lower() in lower_mapping:
                    return lower_mapping[value.lower()]
        return value


class Conversation(Base):
    """Conversation model for storing chat sessions."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True, comment="User-assigned or auto-generated thread name")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    context_objects = relationship("ChatContext", back_populates="conversation", cascade="all, delete-orphan")
    
    def get_message_count(self) -> int:
        """Get the count of messages in this conversation."""
        return len(self.messages) if self.messages else 0
    
    def get_display_name(self, max_length: int = 50) -> str:
        """Get display name, either user-assigned or auto-generated from first message."""
        if self.name:
            return self.name
        
        # Try to generate from first user message
        if self.messages:
            first_user_message = next((m for m in self.messages if m.role == MessageRole.USER), None)
            if first_user_message and first_user_message.content:
                # Take first max_length characters, truncate at word boundary if possible
                content = first_user_message.content.strip()
                if len(content) <= max_length:
                    return content
                # Truncate and add ellipsis
                truncated = content[:max_length].rsplit(' ', 1)[0]  # Try to break at word boundary
                return truncated + '...' if len(truncated) < len(content) else content[:max_length] + '...'
        
        # Fallback to "Chat {id}"
        return f"Chat {self.id}"

    def __repr__(self):
        return f"<Conversation(id={self.id}, created_at={self.created_at})>"


class Message(Base):
    """Message model for storing individual chat messages."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(MessageRoleType(), nullable=False)
    content = Column(Text, nullable=False)  # Max length enforced at application level
    model_used = Column(String(100), nullable=True)  # e.g., 'gpt-4', 'gemini-pro'
    tokens_used = Column(BigInteger, nullable=True)  # For cost tracking
    extra_metadata = Column(JSON, nullable=True)  # For structured metadata (function calls, tool usage, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
    )

    @property
    def role_value(self) -> str:
        """Get the role as a lowercase string value."""
        if isinstance(self.role, MessageRole):
            return self.role.value
        if isinstance(self.role, str):
            return self.role.lower()
        return str(self.role).lower()

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"


class Session(Base):
    """Session model for tracking user sessions."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)  # Optional user identifier
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_session_user_active", "user_id", "last_active"),
    )

    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, last_active={self.last_active})>"


class ChatContext(Base):
    """Chat context model for storing objects in conversation context."""
    __tablename__ = "chat_contexts"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(String(255), nullable=False, comment="Object ID (datasource or view)")
    object_type = Column(String(50), nullable=False, comment="Object type: 'datasource' or 'view'")
    object_name = Column(String(255), nullable=True, comment="Object name for display")
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="context_objects")

    # Indexes
    __table_args__ = (
        Index("idx_context_conversation_object", "conversation_id", "object_id", "object_type"),
    )

    def __repr__(self):
        return f"<ChatContext(id={self.id}, conversation_id={self.conversation_id}, object_type={self.object_type}, object_id={self.object_id})>"
