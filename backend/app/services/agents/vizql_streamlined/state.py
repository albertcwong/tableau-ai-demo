"""State definition for streamlined VizQL agent."""
from typing import TypedDict, Optional, List, Dict, Any
from app.services.agents.base_state import BaseAgentState


class StreamlinedVizQLState(BaseAgentState):
    """
    State for streamlined VizQL agent.
    
    Flow:
    1. build_query: Generate VizQL query using LLM with tools
    2. validate_query: Local validation (no LLM)
    3. execute_query: Execute against Tableau
    4. format_results: Format results (captured in reasoning)
    5. error_handler: Handle errors after max retries
    """
    # Schema (fetched by build_query if needed)
    schema: Optional[Dict[str, Any]]
    enriched_schema: Optional[Dict[str, Any]]  # Optional pre-fetched enriched schema
    datasource_metadata: Optional[Dict[str, Any]]  # REST API metadata
    
    # Query Building
    query_draft: Optional[Dict[str, Any]]
    reasoning: Optional[str]  # LLM reasoning + tool usage
    query_reused: Optional[bool]  # True if from prior message
    
    # Validation
    is_valid: Optional[bool]
    validation_errors: Optional[List[str]]
    validation_suggestions: Optional[List[str]]
    
    # Execution
    query_results: Optional[Dict[str, Any]]
    execution_status: Optional[str]  # "success" | "failed"
    execution_errors: Optional[List[str]]
    
    # Formatting
    formatted_response: Optional[str]
    previous_results: Optional[Dict[str, Any]]
    
    # Control Flow
    attempt: int  # 1, 2, or 3 (defaults to 1)
    query_version: int  # Track refinement iterations (defaults to 0)
    
    # Reasoning Capture (NEW)
    reasoning_steps: Optional[List[Dict[str, Any]]]  # Capture all reasoning including format
    
    # Step Metadata (for detailed reasoning display)
    step_metadata: Optional[Dict[str, Any]]  # Per-step metadata: tool_calls, tokens, etc.
    
    # Error Handling
    error_summary: Optional[Dict[str, Any]]
