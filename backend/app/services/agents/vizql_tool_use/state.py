"""State definition for tool-use VizQL agent."""
from typing import TypedDict, Optional, List, Dict, Any


class VizQLToolUseState(TypedDict, total=False):
    """
    Simplified state for tool-use agent.
    
    2-step flow:
    1. get_data: Use tools to retrieve data
    2. summarize: Format data into response
    """
    # Input
    user_query: str
    message_history: List[Dict[str, Any]]
    
    # Step 1: Get Data
    raw_data: Optional[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]  # Track which tools were used
    current_thought: Optional[str]  # For reasoning steps
    query_draft: Optional[Dict[str, Any]]  # VizQL query for extraction
    
    # Step 2: Summarize
    final_answer: Optional[str]
    
    # Error handling
    error: Optional[str]
    
    # Context (optional)
    datasource_id: Optional[str]
    site_id: Optional[str]
    
    # AI client configuration (REQUIRED - must be in state)
    api_key: Optional[str]
    model: Optional[str]
