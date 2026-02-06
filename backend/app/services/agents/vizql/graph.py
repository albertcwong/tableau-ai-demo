"""VizQL agent graph implementation."""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.vizql.state import VizQLAgentState
from app.services.agents.vizql.nodes.router import route_query_node
from app.services.agents.vizql.nodes.schema_handler import handle_schema_query_node
from app.services.agents.vizql.nodes.reformatter import reformat_results_node
from app.services.agents.vizql.nodes.planner import plan_query_node
from app.services.agents.vizql.nodes.schema_fetch import fetch_schema_node
from app.services.agents.vizql.nodes.query_builder import build_query_node
from app.services.agents.vizql.nodes.validator import validate_query_node
from app.services.agents.vizql.nodes.refiner import refine_query_node
from app.services.agents.vizql.nodes.executor import execute_query_node
from app.services.agents.vizql.nodes.formatter import format_results_node

logger = logging.getLogger(__name__)


def create_vizql_graph() -> StateGraph:
    """
    Create VizQL agent graph with ReAct pattern and intelligent routing.
    
    Graph flow:
    1. Router -> Classify query type
    2a. If schema_query -> Schema Handler -> END
    2b. If reformat_previous -> Reformatter -> END
    2c. If new_query -> Planner -> Schema Fetch -> Query Builder -> Validator
    3. Validator -> (if valid) Executor -> Formatter -> END
    4. Validator -> (if invalid) Refiner -> Validator (loop, max 3 times)
    5. Refiner -> (if max attempts) END with error
    """
    workflow = StateGraph(VizQLAgentState)
    
    # Add nodes
    workflow.add_node("router", route_query_node)  # NEW: Router for query classification
    workflow.add_node("schema_handler", handle_schema_query_node)  # NEW: Schema query handler
    workflow.add_node("reformatter", reformat_results_node)  # NEW: Result reformatter
    workflow.add_node("planner", plan_query_node)
    workflow.add_node("schema_fetch", fetch_schema_node)
    workflow.add_node("query_builder", build_query_node)
    workflow.add_node("validator", validate_query_node)
    workflow.add_node("refiner", refine_query_node)
    workflow.add_node("executor", execute_query_node)
    workflow.add_node("formatter", format_results_node)
    
    # Set entry point to router (changed from planner)
    workflow.set_entry_point("router")
    
    # Conditional routing from router
    def route_from_router(state: VizQLAgentState) -> str:
        """Route based on query classification."""
        query_type = state.get("query_type", "new_query")
        logger.info(f"Routing query as '{query_type}'")
        
        if query_type == "schema_query":
            return "schema_handler"
        elif query_type == "reformat_previous":
            return "reformatter"
        else:  # new_query
            return "planner"
    
    workflow.add_conditional_edges(
        "router",
        route_from_router,
        {
            "schema_handler": "schema_handler",
            "reformatter": "reformatter",
            "planner": "planner"
        }
    )
    
    # Schema handler and reformatter go directly to END
    workflow.add_edge("schema_handler", END)
    workflow.add_edge("reformatter", END)
    
    # Add edges for normal query flow
    workflow.add_edge("planner", "schema_fetch")
    workflow.add_edge("schema_fetch", "query_builder")
    workflow.add_edge("query_builder", "validator")
    
    # Error handler node to format errors as final_answer
    async def error_handler_node(state: VizQLAgentState) -> Dict[str, Any]:
        """Handle errors and format as final_answer."""
        error = state.get("error")
        execution_error = state.get("execution_error")
        validation_errors = state.get("validation_errors", [])
        validation_suggestions = state.get("validation_suggestions", [])
        
        error_message = "❌ Query execution failed.\n\n"
        
        if error:
            error_message += f"**Error:** {error}\n\n"
        elif execution_error:
            error_message += f"**Execution Error:** {execution_error}\n\n"
        elif validation_errors:
            error_message += f"**Validation Errors:**\n"
            for err in validation_errors:
                error_message += f"- {err}\n"
            error_message += "\n"
        
        if validation_suggestions:
            error_message += f"**Suggestions:**\n"
            for sug in validation_suggestions:
                error_message += f"- {sug}\n"
        
        return {
            **state,
            "final_answer": error_message,
            "error": error or execution_error or (validation_errors[0] if validation_errors else None)
        }
    
    workflow.add_node("error_handler", error_handler_node)
    
    # Conditional routing from validator
    def route_after_validation(state: VizQLAgentState) -> str:
        """Route based on validation result."""
        # Check for errors first
        if state.get("error"):
            return "error_handler"
        
        # Check validation result
        if state.get("is_valid", False):
            return "execute"
        
        # Invalid query - check if we can refine
        # Allow up to 3 refinement attempts (query_version 1, 2, 3)
        # After 3 refinements, query_version will be 4, so stop
        query_version = state.get("query_version", 0)
        if query_version >= 4:
            return "error_handler"
        
        return "refine"
    
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "execute": "executor",
            "refine": "refiner",
            "error_handler": "error_handler"
        }
    )
    
    # Handle errors in executor
    def route_after_execution(state: VizQLAgentState) -> str:
        """Route after execution - check for errors."""
        if state.get("error") or state.get("execution_error"):
            return "error_handler"  # Route to error handler
        return "formatter"
    
    workflow.add_conditional_edges(
        "executor",
        route_after_execution,
        {
            "formatter": "formatter",
            "error_handler": "error_handler"
        }
    )
    
    # Refiner loops back to validator (not query_builder, to avoid regenerating the query)
    workflow.add_edge("refiner", "validator")
    
    # Executor routing handled by conditional edges above
    
    # Formatter and error handler end
    workflow.add_edge("formatter", END)
    workflow.add_edge("error_handler", END)
    
    # Compile with checkpointing for resumability
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
