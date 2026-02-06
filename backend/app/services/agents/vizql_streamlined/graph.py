"""Streamlined VizQL agent graph implementation."""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.agents.vizql_streamlined.nodes import (
    build_query_node,
    validate_query_node,
    execute_query_node,
    format_results_node,
    error_handler_node
)

logger = logging.getLogger(__name__)


def create_streamlined_vizql_graph() -> StateGraph:
    """
    Create streamlined VizQL agent graph.
    
    Graph flow:
    1. build_query -> Generate VizQL query (with tools, can reuse prior queries)
    2. validate_query -> Local validation
    3. execute_query -> Execute against Tableau
    4. format_results -> Format results (captured in reasoning)
    5. error_handler -> Handle errors after max retries
    
    Retry logic:
    - If validation fails and attempt < 3: retry build_query
    - If execution fails and attempt < 3: retry build_query
    - After max attempts: route to error_handler
    """
    workflow = StateGraph(StreamlinedVizQLState)
    
    # Add nodes
    workflow.add_node("build_query", build_query_node)
    workflow.add_node("validate_query", validate_query_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_results", format_results_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set entry point
    workflow.set_entry_point("build_query")
    
    # Add edges
    workflow.add_edge("build_query", "validate_query")
    
    # Conditional routing from validator
    def route_after_validation(state: StreamlinedVizQLState) -> str:
        """Route based on validation result."""
        # Check for errors first
        if state.get("error"):
            return "error_handler"
        
        # Check validation result
        if state.get("is_valid", False):
            return "execute"
        
        # Invalid query - check if we can retry
        attempt = state.get("attempt", 1)
        if attempt >= 3:
            return "error_handler"
        
        # Retry build_query with errors (attempt will be incremented in build_query node)
        return "retry"
    
    workflow.add_conditional_edges(
        "validate_query",
        route_after_validation,
        {
            "execute": "execute_query",
            "retry": "build_query",
            "error_handler": "error_handler"
        }
    )
    
    # Conditional routing from executor
    def route_after_execution(state: StreamlinedVizQLState) -> str:
        """Route after execution - check for errors."""
        if state.get("execution_status") == "success":
            return "format"
        
        # Execution failed - check if we can retry
        attempt = state.get("attempt", 1)
        if attempt >= 3:
            return "error_handler"
        
        # Retry build_query with errors (attempt will be incremented in build_query node)
        return "retry"
    
    workflow.add_conditional_edges(
        "execute_query",
        route_after_execution,
        {
            "format": "format_results",
            "retry": "build_query",
            "error_handler": "error_handler"
        }
    )
    
    # Terminal nodes
    workflow.add_edge("format_results", END)
    workflow.add_edge("error_handler", END)
    
    # Compile with checkpointing for resumability
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
