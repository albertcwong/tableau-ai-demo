"""State definition for VizQL agent."""
from typing import TypedDict, Optional, Any
from app.services.agents.base_state import BaseAgentState


class VizQLAgentState(BaseAgentState):
    """State for VizQL agent graph."""
    
    # Schema information
    schema: Optional[dict]
    enriched_schema: Optional[dict]  # Enriched schema from Phase 2 (with semantic metadata)
    
    # Intent parsing results
    required_measures: list[str]
    required_dimensions: list[str]
    required_filters: dict[str, Any]  # Structured filters with filterType and params
    topN: Optional[dict[str, Any]]  # Top N pattern: {enabled, howMany, direction, dimensionField, measureField}
    sorting: list[dict[str, Any]]  # Sorting requirements: [{field, direction, priority}]
    calculations: list[dict[str, Any]]  # Ad-hoc calculations: [{fieldCaption, formula}]
    bins: list[dict[str, Any]]  # Bin requirements: [{fieldCaption, binSize}]
    
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
