"""Streamlined VizQL agent graph implementation."""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.agents.vizql_streamlined.nodes import (
    start_node,
    build_query_node,
    pre_validation_node,
    validate_query_node,
    execute_query_node,
    format_results_node,
    error_handler_node
)
from app.core.config import settings

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
    - If validation fails and build_attempt <= VIZQL_MAX_BUILD_RETRIES: retry build_query
    - If execution fails and execution_attempt <= VIZQL_MAX_EXECUTION_RETRIES: retry build_query (resets build_attempt)
    - After max attempts: route to error_handler
    """
    workflow = StateGraph(StreamlinedVizQLState)
    
    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("build_query", build_query_node)
    workflow.add_node("pre_validation", pre_validation_node)
    workflow.add_node("validate_query", validate_query_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_results", format_results_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set entry point (start returns immediately to kick off frontend timer)
    workflow.set_entry_point("start")
    
    # Add edges
    workflow.add_edge("start", "build_query")
    workflow.add_edge("build_query", "pre_validation")
    workflow.add_edge("pre_validation", "validate_query")
    
    # Conditional routing from validator
    def route_after_validation(state: StreamlinedVizQLState) -> str:
        """Route based on validation result."""
        is_valid = state.get("is_valid", False)
        build_attempt = state.get("build_attempt", 1)
        max_build_retries = settings.VIZQL_MAX_BUILD_RETRIES
        error = state.get("error")
        
        logger.info(f"route_after_validation: is_valid={is_valid}, build_attempt={build_attempt}, max={max_build_retries}, error={error}")
        
        # Check for errors first
        if error:
            logger.info("Routing to error_handler (error present)")
            return "error_handler"
        
        # Check validation result
        if is_valid:
            logger.info("Routing to execute_query (validation passed)")
            return "execute"
        
        # Invalid query - check if we can retry build
        if build_attempt > max_build_retries:
            logger.info(f"Routing to error_handler (build_attempt {build_attempt} > max {max_build_retries})")
            return "error_handler"
        
        # Retry build_query with errors (build_attempt will be incremented in build_query node)
        logger.info(f"Routing to retry build_query (build_attempt {build_attempt} <= max {max_build_retries})")
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
        execution_status = state.get("execution_status")
        execution_attempt = state.get("execution_attempt", 1)
        max_execution_retries = settings.VIZQL_MAX_EXECUTION_RETRIES
        
        logger.info(f"route_after_execution: execution_status={execution_status}, execution_attempt={execution_attempt}, max={max_execution_retries}")
        
        if execution_status == "success":
            logger.info("Routing to format_results (execution successful)")
            return "format"
        
        # Execution failed - check if we can retry execution
        # execution_attempt will be incremented in query_builder, so check if next attempt would exceed max
        if execution_attempt >= max_execution_retries:
            logger.info(f"Routing to error_handler (execution_attempt {execution_attempt} >= max {max_execution_retries})")
            return "error_handler"
        
        # Retry build_query with errors
        # build_attempt will be reset to 1 in query_builder when retrying after execution failure
        logger.info(f"Routing to retry build_query (execution_attempt {execution_attempt} < max {max_execution_retries})")
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
