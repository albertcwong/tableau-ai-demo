"""AI service response models."""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ChatMessage:
    """Chat message model."""
    role: str  # "user", "assistant", "system"
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


@dataclass
class FunctionCall:
    """Function call model."""
    name: str
    arguments: str  # JSON string


@dataclass
class ChatResponse:
    """Chat completion response model."""
    content: str
    model: str
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    function_call: Optional[FunctionCall] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class StreamChunk:
    """Streaming chunk model."""
    content: str
    finish_reason: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    raw_chunk: Optional[Dict[str, Any]] = None
