"""State definition for controlled VizQL agent graph."""
from typing import TypedDict, Optional, List, Dict, Any


class VizQLGraphState(TypedDict, total=False):
    """
    State schema for controlled VizQL query graph.
    
    Flow:
    1. start: Initialize workflow
    2. get_schema: Fetch datasource metadata
    3. build_query: Generate VizQL query using LLM
    4. validate_query: Local validation (no LLM)
    5. execute_query: Execute against Tableau
    6. summarize: Format results
    7. error_handler: Handle errors after max retries
    """
    # Input
    user_query: str
    datasource_id: str
    site_id: str
    message_history: List[Dict[str, Any]]
    api_key: str
    model: str
    
    # Schema
    schema: Optional[Dict[str, Any]]
    metadata_stats: Optional[Dict[str, Any]]
    
    # Query Building
    query_draft: Optional[Dict[str, Any]]
    reasoning: Optional[str]
    
    # Validation
    validated_query: Optional[Dict[str, Any]]
    validation_errors: Optional[List[str]]
    validation_status: Optional[str]  # "valid" or "invalid"
    
    # Execution
    raw_data: Optional[Dict[str, Any]]
    execution_errors: Optional[List[str]]
    execution_status: Optional[str]  # "success" or "failed"
    
    # Summarization
    final_answer: Optional[str]
    shown_entities: Optional[Dict[str, Any]]
    
    # Control Flow
    attempt: int  # 1, 2, or 3
    current_thought: Optional[str]
    
    # Error Handling
    schema_error: Optional[str]
    build_error: Optional[str]
    timeout_error: Optional[str]
    auth_error: Optional[str]
    error_summary: Optional[Dict[str, Any]]