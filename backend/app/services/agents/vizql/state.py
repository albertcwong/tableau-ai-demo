"""State definition for VizQL agent."""
from typing import TypedDict, Optional, Any
from app.services.agents.base_state import BaseAgentState


class VizQLAgentState(BaseAgentState):
    """State for VizQL agent graph."""
    
    # Schema information
    schema: Optional[dict]
    
    # Intent parsing results
    required_measures: list[str]
    required_dimensions: list[str]
    required_filters: dict[str, Any]
    
    # Query construction
    query_draft: Optional[dict]
    query_version: int  # Track refinement iterations (max 3)
    
    # Validation
    is_valid: bool
    validation_errors: list[str]
    validation_suggestions: list[str]
    
    # Execution
    query_results: Optional[dict]
    execution_error: Optional[str]
