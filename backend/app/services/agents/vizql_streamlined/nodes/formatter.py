"""Formatter node for formatting query results with reasoning capture."""
import json
import logging
from typing import Dict, Any
from datetime import datetime

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.metrics import track_node_execution
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient

logger = logging.getLogger(__name__)


def format_as_table(columns: list, data: list, max_rows: int = 10) -> str:
    """Format data as a simple text table."""
    if not columns or not data:
        return "No data to display"
    
    # Limit rows
    display_data = data[:max_rows]
    
    # Calculate column widths
    col_widths = {}
    for col in columns:
        col_widths[col] = len(str(col))
    
    for row in display_data:
        for i, col in enumerate(columns):
            if i < len(row):
                val_len = len(str(row[i]))
                col_widths[col] = max(col_widths[col], val_len)
    
    # Build table
    lines = []
    
    # Header
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    lines.append(header)
    lines.append("-" * len(header))
    
    # Rows
    for row in display_data:
        row_str = " | ".join(
            str(row[i] if i < len(row) else "").ljust(col_widths[col])
            for i, col in enumerate(columns)
        )
        lines.append(row_str)
    
    return "\n".join(lines)


@track_node_execution("vizql_streamlined", "formatter")
async def format_results_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Format query results for user presentation using AI to generate natural language answer.
    
    This step is captured in reasoning_steps.
    """
    results = state.get("query_results")
    user_query = state.get("user_query", "")
    reasoning_steps = state.get("reasoning_steps", [])
    
    if not results:
        reasoning_steps.append({
            "node": "format_results",
            "timestamp": datetime.utcnow().isoformat(),
            "thought": "No results to format",
            "action": "format",
            "output_length": 0
        })
        return {
            **state,
            "formatted_response": "No results to format",
            "final_answer": "Query executed but returned no results.",
            "reasoning_steps": reasoning_steps,
            "current_thought": None
        }
    
    try:
        # Get AI client configuration from state
        model = state.get("model") or "gpt-4"
        provider = state.get("provider", "openai")
        
        # Prepare data for AI formatting
        columns = results.get("columns", [])
        data = results.get("data", [])
        row_count = results.get("row_count", 0)
        
        # Format data sample (first 1000 rows for context)
        sample_size = min(1000, len(data))
        data_sample = ""
        if columns and data:
            data_sample = format_as_table(columns, data, max_rows=sample_size)
        
        # Get query draft to check if TOP filter was used
        query_draft = state.get("query_draft", {})
        query_draft_str = json.dumps(query_draft, indent=2) if query_draft else "No query draft available"
        
        # Check if query has TOP filter
        has_top_filter = False
        if query_draft and "query" in query_draft:
            filters = query_draft.get("query", {}).get("filters", [])
            has_top_filter = any(
                f.get("filterType") == "TOP" for f in filters if isinstance(f, dict)
            )
        
        # Load and render prompt template with data
        prompt_content = prompt_registry.get_prompt(
            "agents/vizql/result_formatting.txt",
            variables={
                "user_query": user_query,
                "query_draft": query_draft_str,
                "columns": ", ".join(columns) if columns else "N/A",
                "row_count": row_count,
                "total_rows": row_count,
                "sample_size": sample_size,
                "data_sample": data_sample
            }
        )
        
        # Call AI to generate natural language answer
        logger.info(f"Generating natural language answer for query results ({row_count} rows)")
        from app.core.config import settings
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful data analyst assistant that explains query results in clear, natural language."},
            {"role": "user", "content": prompt_content}
        ]
        
        ai_response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        # Track token usage
        tokens_used = {
            "prompt": ai_response.prompt_tokens,
            "completion": ai_response.completion_tokens,
            "total": ai_response.tokens_used
        }
        
        final_answer = ai_response.content if ai_response.content else "Query executed successfully, but could not generate answer."
        
        logger.info(f"Generated answer: {len(final_answer)} characters")
        
        # Capture formatting in reasoning steps
        reasoning_steps.append({
            "node": "format_results",
            "timestamp": datetime.utcnow().isoformat(),
            "thought": f"Formatted {row_count} rows into natural language",
            "action": "format",
            "output_length": len(final_answer)
        })
        
        return {
            **state,
            "formatted_response": final_answer,
            "final_answer": final_answer,
            "previous_results": results,
            "reasoning_steps": reasoning_steps,
            "current_thought": None,
            "step_metadata": {
                "tool_calls": [],
                "tokens": tokens_used
            }
        }
        
    except Exception as e:
        logger.error(f"Error formatting results with AI: {e}", exc_info=True)
        # Fallback to basic formatting
        return await _format_basic_response(state, results, reasoning_steps)


async def _format_basic_response(state: StreamlinedVizQLState, results: Dict[str, Any], reasoning_steps: list) -> Dict[str, Any]:
    """Fallback basic formatting without AI."""
    row_count = results.get("row_count", 0)
    columns = results.get("columns", [])
    data = results.get("data", [])
    
    response = f"✅ Query executed successfully!\n\n"
    response += f"**Results:** Found {row_count} row{'s' if row_count != 1 else ''}.\n\n"
    
    if columns and data:
        response += "**Data Preview:**\n"
        response += "```\n"
        response += format_as_table(columns, data, max_rows=1000)
        response += "\n```\n\n"
        
        if row_count > 10:
            response += f"_(Showing first 10 of {row_count} rows)_\n\n"
    
    reasoning_steps.append({
        "node": "format_results",
        "timestamp": datetime.utcnow().isoformat(),
        "thought": f"Formatted {row_count} rows using basic formatting",
        "action": "format",
        "output_length": len(response)
    })
    
    return {
        **state,
        "formatted_response": response,
        "final_answer": response,
        "previous_results": results,
        "reasoning_steps": reasoning_steps,
        "current_thought": None
    }
