"""Error handler node - generate helpful error message after max retries."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState

logger = logging.getLogger(__name__)


async def error_handler_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Generate helpful error message after max retries.
    
    Operations:
    1. Summarize what was tried
    2. Explain what went wrong
    3. Suggest next steps for user
    4. Log full error context
    
    Duration: 1000-2000ms
    """
    user_query = state.get("user_query", "")
    attempt = state.get("attempt", 1)
    validation_errors = state.get("validation_errors", [])
    execution_errors = state.get("execution_errors", [])
    schema_error = state.get("schema_error")
    query_draft = state.get("query_draft", {})
    schema = state.get("schema", {})
    
    # Build error summary
    error_parts = []
    
    if schema_error:
        error_parts.append(f"Schema Error: {schema_error}")
    
    if validation_errors:
        error_parts.append(f"Validation Errors (attempt {attempt}):")
        for i, err in enumerate(validation_errors, 1):
            error_parts.append(f"  {i}. {err}")
    
    if execution_errors:
        error_parts.append(f"Execution Errors (attempt {attempt}):")
        for i, err in enumerate(execution_errors, 1):
            error_parts.append(f"  {i}. {err}")
    
    # Build helpful error message
    error_summary = {
        "attempts": attempt,
        "errors": error_parts,
        "query_draft": query_draft
    }
    
    # Generate user-friendly message
    message_parts = [
        f"I tried {attempt} time{'s' if attempt > 1 else ''} to build a query for your question but encountered errors:",
        ""
    ]
    
    if validation_errors:
        message_parts.append("Validation Issues:")
        for err in validation_errors[:5]:  # Limit to 5 errors
            message_parts.append(f"- {err}")
        message_parts.append("")
    
    if execution_errors:
        message_parts.append("Execution Issues:")
        for err in execution_errors[:5]:  # Limit to 5 errors
            message_parts.append(f"- {err}")
        message_parts.append("")
    
    # Add schema info if available
    if schema:
        measures = schema.get("measures", [])
        dimensions = schema.get("dimensions", [])
        
        if measures or dimensions:
            message_parts.append("The dataset has these fields:")
            if measures:
                message_parts.append(f"- Measures: {', '.join(measures[:10])}")
            if dimensions:
                message_parts.append(f"- Dimensions: {', '.join(dimensions[:10])}")
            message_parts.append("")
    
    message_parts.append("Could you rephrase your question or clarify which fields you'd like to query?")
    
    final_answer = "\n".join(message_parts)
    
    logger.error(f"Error handler: {attempt} attempts, {len(error_parts)} error types")
    
    return {
        **state,
        "final_answer": final_answer,
        "error_summary": error_summary,
        "current_thought": "Handling errors..."
    }