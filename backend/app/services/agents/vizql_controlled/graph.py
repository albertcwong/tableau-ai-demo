"""Controlled VizQL agent graph - predictable flow with explicit nodes."""
import logging
from langgraph.graph import StateGraph, END

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.agents.vizql_controlled.nodes.start import start_node
from app.services.agents.vizql_controlled.nodes.get_schema import get_schema_node
from app.services.agents.vizql_controlled.nodes.build_query import build_query_node
from app.services.agents.vizql_controlled.nodes.validate_query import validate_query_node
from app.services.agents.vizql_controlled.nodes.execute_query import execute_query_node
from app.services.agents.vizql_controlled.nodes.summarize import summarize_node
from app.services.agents.vizql_controlled.nodes.error_handler import error_handler_node

logger = logging.getLogger(__name__)


def route_after_schema(state: VizQLGraphState) -> str:
    """Route after schema fetch."""
    if state.get("schema_error"):
        return "error"
    return "build_query"


def route_after_validation(state: VizQLGraphState) -> str:
    """Route after query validation."""
    validation_status = state.get("validation_status")
    attempt = state.get("attempt", 1)
    
    if validation_status == "valid":
        return "execute"
    elif attempt < 3:
        return "retry"
    return "error"


def route_after_execution(state: VizQLGraphState) -> str:
    """Route after query execution."""
    execution_status = state.get("execution_status")
    attempt = state.get("attempt", 1)
    
    if execution_status == "success":
        return "summarize"
    elif attempt < 3:
        # Check error type - only retry syntax errors, not auth/timeout
        if state.get("auth_error") or state.get("timeout_error"):
            return "error"
        return "retry"
    return "error"


def create_vizql_controlled_graph():
    """
    Create controlled VizQL query graph.
    
    Flow:
    1. start: Initialize workflow
    2. get_schema: Fetch datasource metadata
    3. build_query: Generate VizQL query using LLM
    4. validate_query: Local validation (no LLM)
    5. execute_query: Execute against Tableau
    6. summarize: Format results
    7. error_handler: Handle errors after max retries
    """
    graph = StateGraph(VizQLGraphState)
    
    # Add nodes
    graph.add_node("start", start_node)
    graph.add_node("get_schema", get_schema_node)
    graph.add_node("build_query", build_query_node)
    graph.add_node("validate_query", validate_query_node)
    graph.add_node("execute_query", execute_query_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)
    
    # Linear flow
    graph.set_entry_point("start")
    graph.add_edge("start", "get_schema")
    
    # Conditional from get_schema
    graph.add_conditional_edges(
        "get_schema",
        route_after_schema,
        {
            "build_query": "build_query",
            "error": "error_handler"
        }
    )
    
    graph.add_edge("build_query", "validate_query")
    
    # Conditional from validate_query
    graph.add_conditional_edges(
        "validate_query",
        route_after_validation,
        {
            "execute": "execute_query",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    # Conditional from execute_query
    graph.add_conditional_edges(
        "execute_query",
        route_after_execution,
        {
            "summarize": "summarize",
            "retry": "build_query",
            "error": "error_handler"
        }
    )
    
    # Terminal nodes
    graph.add_edge("summarize", END)
    graph.add_edge("error_handler", END)
    
    logger.info("Controlled VizQL agent graph created")
    
    return graph.compile()


# Singleton instance
_agent_instance = None


def get_vizql_controlled_agent():
    """Get singleton instance of controlled VizQL agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_vizql_controlled_graph()
    return _agent_instance