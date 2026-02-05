"""Formatter node for formatting query results."""
import json
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
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


@track_node_execution("vizql", "formatter")
async def format_results_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Format query results for user presentation using AI to generate natural language answer.
    
    This is a final "Act" step in ReAct.
    """
    results = state.get("query_results")
    user_query = state.get("user_query", "")
    
    if not results:
        return {
            **state,
            "formatted_response": "No results to format",
            "final_answer": "Query executed but returned no results."
        }
    
    try:
        # Get AI client configuration from state
        api_key = state.get("api_key")
        model = state.get("model") or "gpt-4"
        
        if not api_key:
            logger.warning("No API key in state, falling back to basic formatting")
            return await _format_basic_response(state, results)
        
        # Prepare data for AI formatting
        columns = results.get("columns", [])
        data = results.get("data", [])
        row_count = results.get("row_count", 0)
        
        # Format data sample (first 20 rows for context)
        sample_size = min(20, len(data))
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
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful data analyst assistant that explains query results in clear, natural language."},
            {"role": "user", "content": prompt_content}
        ]
        
        ai_response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        final_answer = ai_response.content if ai_response.content else "Query executed successfully, but could not generate answer."
        
        logger.info(f"Generated answer: {len(final_answer)} characters")
        
        return {
            **state,
            "formatted_response": final_answer,
            "final_answer": final_answer,
            "current_thought": None  # Clear thought as we're done
        }
        
    except Exception as e:
        logger.error(f"Error formatting results with AI: {e}", exc_info=True)
        # Fallback to basic formatting
        return await _format_basic_response(state, results)


async def _format_basic_response(state: VizQLAgentState, results: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback basic formatting without AI."""
    row_count = results.get("row_count", 0)
    columns = results.get("columns", [])
    data = results.get("data", [])
    
    response = f"✅ Query executed successfully!\n\n"
    response += f"**Results:** Found {row_count} row{'s' if row_count != 1 else ''}.\n\n"
    
    if columns and data:
        response += "**Data Preview:**\n"
        response += "```\n"
        response += format_as_table(columns, data, max_rows=10)
        response += "\n```\n\n"
        
        if row_count > 10:
            response += f"_(Showing first 10 of {row_count} rows)_\n\n"
    
    return {
        **state,
        "formatted_response": response,
        "final_answer": response,
        "current_thought": None
    }
