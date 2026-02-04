"""Base state definitions for LangGraph agents."""
from typing import TypedDict, Annotated, Sequence, Optional, Any
from langchain_core.messages import BaseMessage


class BaseAgentState(TypedDict):
    """Base state shared across all agent types."""
    
    # Input
    user_query: str
    agent_type: str
    context_datasources: list[str]
    context_views: list[str]
    
    # Conversation history (can be BaseMessage objects or dicts with role/content)
    messages: Annotated[Sequence[Any], "conversation messages"]
    
    # Tool calls tracking
    tool_calls: list[dict]
    tool_results: list[dict]
    
    # Current processing state
    current_thought: Optional[str]
    
    # Output
    final_answer: Optional[str]
    error: Optional[str]
    
    # Metadata
    confidence: Optional[float]
    processing_time: Optional[float]
    
    # AI client configuration
    api_key: Optional[str]
    model: Optional[str]
