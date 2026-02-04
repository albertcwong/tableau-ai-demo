"""VizQL agent graph implementation."""
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.vizql.state import VizQLAgentState
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
    Create VizQL agent graph with ReAct pattern.
    
    Graph flow:
    1. Planner -> Schema Fetch -> Query Builder -> Validator
    2. Validator -> (if valid) Executor -> Formatter -> END
    3. Validator -> (if invalid) Refiner -> Query Builder (loop, max 3 times)
    4. Refiner -> (if max attempts) END with error
    """
    workflow = StateGraph(VizQLAgentState)
    
    # Add nodes
    workflow.add_node("planner", plan_query_node)
    workflow.add_node("schema_fetch", fetch_schema_node)
    workflow.add_node("query_builder", build_query_node)
    workflow.add_node("validator", validate_query_node)
    workflow.add_node("refiner", refine_query_node)
    workflow.add_node("executor", execute_query_node)
    workflow.add_node("formatter", format_results_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edges
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
        query_version = state.get("query_version", 0)
        if query_version >= 3:
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
    
    # Refiner loops back to query_builder
    workflow.add_edge("refiner", "query_builder")
    
    # Executor routing handled by conditional edges above
    
    # Formatter and error handler end
    workflow.add_edge("formatter", END)
    workflow.add_edge("error_handler", END)
    
    # Compile with checkpointing for resumability
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
