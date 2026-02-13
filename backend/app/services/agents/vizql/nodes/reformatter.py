"""Result reformatter node for reformatting previous query results."""
import json
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


def format_data_as_table(columns: list, data: list, max_rows: int = 1000) -> str:
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


@track_node_execution("vizql", "reformatter")
async def reformat_results_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Reformat previous query results based on user request.
    
    Takes query_results from state and reformats according to user's request
    (table, summary, top N, etc.)
    """
    try:
        user_query = state.get("user_query", "")
        previous_results = state.get("previous_results")
        
        if not previous_results or not previous_results.get("data"):
            return {
                **state,
                "final_answer": "I don't have any previous results to reformat. Please run a query first.",
                "error": "No previous results available"
            }
        
        # Extract data from previous results
        columns = previous_results.get("columns", [])
        data = previous_results.get("data", [])
        row_count = len(data)
        
        # Get query that generated these results (if available)
        original_query = state.get("query_draft", {})
        original_query_str = json.dumps(original_query, indent=2) if original_query else "Query not available"
        
        # Format data sample for prompt (up to 1000 rows)
        sample_size = min(1000, row_count)
        data_sample = format_data_as_table(columns, data, max_rows=sample_size)
        
        # Get reformatter prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/result_reformatter.txt",
            variables={
                "user_query": user_query,
                "original_query": original_query_str,
                "columns": ", ".join(columns) if columns else "N/A",
                "row_count": row_count,
                "data_sample": data_sample,
                "sample_size": sample_size
            }
        )
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        # Call LLM to reformat results
        messages = [
            {"role": "system", "content": "You are a helpful assistant that reformats data according to user requests."},
            {"role": "user", "content": system_prompt}
        ]
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        reformatted_answer = response.content if response.content else "I couldn't reformat the results."
        
        logger.info(f"Results reformatted: {len(reformatted_answer)} characters")
        
        return {
            **state,
            "final_answer": reformatted_answer,
            "formatted_response": reformatted_answer,
            "current_thought": None  # Clear thought as we're done
        }
        
    except Exception as e:
        logger.error(f"Error reformatting results: {e}", exc_info=True)
        return {
            **state,
            "final_answer": f"Error reformatting results: {str(e)}",
            "error": str(e)
        }
