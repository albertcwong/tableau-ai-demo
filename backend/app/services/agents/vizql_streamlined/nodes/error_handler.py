"""Error handler node for handling errors after max retries."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql_streamlined", "error_handler")
async def error_handler_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Handle errors and format as final_answer.
    
    Called after max retries are reached.
    """
    error = state.get("error")
    execution_errors = state.get("execution_errors", [])
    build_errors = state.get("build_errors", [])
    validation_errors = state.get("validation_errors", [])
    validation_suggestions = state.get("validation_suggestions", [])
    build_attempt = state.get("build_attempt", 1)
    execution_attempt = state.get("execution_attempt", 1)
    
    error_message = "❌ Query execution failed.\n\n"
    
    # Count actual execution attempts from reasoning_steps
    reasoning_steps = state.get("reasoning_steps", [])
    execution_attempts = len([step for step in reasoning_steps if step.get("node") == "execute_query"])
    
    # If no execution attempts found in reasoning, check if we have execution errors
    if execution_attempts == 0 and execution_errors:
        execution_attempts = 1
    
    # Count build attempts (query builds that happened)
    build_attempts = len([step for step in reasoning_steps if step.get("node") == "build_query"])
    if build_attempts == 0:
        build_attempts = build_attempt
    
    # Total attempts = number of times we actually executed
    total_attempts = execution_attempts
    
    if total_attempts > 1:
        error_message += f"I tried {total_attempts} times to build and execute your query but encountered errors:\n\n"
    elif total_attempts == 1:
        error_message += f"I tried to build and execute your query but encountered errors:\n\n"
    
    if error:
        error_message += f"**Error:** {error}\n\n"
    
    # Show build errors separately if they exist
    if build_errors:
        error_message += f"**Build/Validation Errors:**\n"
        for err in build_errors:
            error_message += f"- {err}\n"
        error_message += "\n"
    elif validation_errors:
        error_message += f"**Validation Errors:**\n"
        for err in validation_errors:
            error_message += f"- {err}\n"
        error_message += "\n"
    
    # Show execution errors separately if they exist
    if execution_errors:
        error_message += f"**Execution Errors:**\n"
        for err in execution_errors:
            error_message += f"- {err}\n"
        error_message += "\n"
    
    if validation_suggestions:
        error_message += f"**Suggestions:**\n"
        for sug in validation_suggestions:
            error_message += f"- {sug}\n"
    
    error_summary = {
        "build_attempt": build_attempt,
        "execution_attempt": execution_attempt,
        "error": error or (execution_errors[0] if execution_errors else None) or (build_errors[0] if build_errors else None) or (validation_errors[0] if validation_errors else None),
        "execution_errors": execution_errors,
        "build_errors": build_errors,
        "validation_errors": validation_errors,
        "validation_suggestions": validation_suggestions
    }
    
    return {
        **state,
        "final_answer": error_message,
        "error": error or (execution_errors[0] if execution_errors else None) or (build_errors[0] if build_errors else None) or (validation_errors[0] if validation_errors else None),
        "error_summary": error_summary
    }
