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
    validation_errors = state.get("validation_errors", [])
    validation_suggestions = state.get("validation_suggestions", [])
    attempt = state.get("attempt", 1)
    
    error_message = "❌ Query execution failed.\n\n"
    
    if attempt > 1:
        error_message += f"I tried {attempt} times to build and execute your query but encountered errors:\n\n"
    
    if error:
        error_message += f"**Error:** {error}\n\n"
    elif execution_errors:
        error_message += f"**Execution Errors:**\n"
        for err in execution_errors:
            error_message += f"- {err}\n"
        error_message += "\n"
    elif validation_errors:
        error_message += f"**Validation Errors:**\n"
        for err in validation_errors:
            error_message += f"- {err}\n"
        error_message += "\n"
    
    if validation_suggestions:
        error_message += f"**Suggestions:**\n"
        for sug in validation_suggestions:
            error_message += f"- {sug}\n"
    
    error_summary = {
        "attempt": attempt,
        "error": error or (execution_errors[0] if execution_errors else None) or (validation_errors[0] if validation_errors else None),
        "execution_errors": execution_errors,
        "validation_errors": validation_errors,
        "validation_suggestions": validation_suggestions
    }
    
    return {
        **state,
        "final_answer": error_message,
        "error": error or (execution_errors[0] if execution_errors else None) or (validation_errors[0] if validation_errors else None),
        "error_summary": error_summary
    }
