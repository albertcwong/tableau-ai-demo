"""Summarizer node for generating final summary."""
import logging
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState

MAX_DATA_ROWS = 50  # Limit rows per view to avoid token overflow


def _format_view_data(views_data: Dict[str, Any], views_metadata: Dict[str, Any]) -> str:
    """Format views_data (columns + rows) as a compact markdown table for prompts."""
    if not views_data:
        return "(No view data available)"
    parts = []
    for view_id, v_data in views_data.items():
        if not v_data:
            continue
        cols = v_data.get("columns", [])
        rows = v_data.get("data", [])[:MAX_DATA_ROWS]
        meta = views_metadata.get(view_id, {})
        name = meta.get("name") or meta.get("id") or view_id
        if not cols:
            parts.append(f"**{name}**: (no columns)")
            continue
        header = " | ".join(str(c) for c in cols)
        sep = " | ".join(["---"] * len(cols))
        table_lines = [f"**{name}**", "", f"| {header} |", f"| {sep} |"]
        for row in rows:
            vals = [str(v)[:50] if v is not None else "" for v in (row if isinstance(row, (list, tuple)) else [row])]
            if len(vals) < len(cols):
                vals.extend([""] * (len(cols) - len(vals)))
            elif len(vals) > len(cols):
                vals = vals[:len(cols)]
            table_lines.append("| " + " | ".join(vals) + " |")
        parts.append("\n".join(table_lines))
    return "\n\n".join(parts) if parts else "(No view data available)"
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


async def summarize_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Generate final natural language summary.
    
    This is a final "Act" step in ReAct.
    """
    try:
        # Check for multiple views
        views_metadata = state.get("views_metadata", {})
        views_data = state.get("views_data", {})
        view_ids = state.get("context_views", [])
        
        # Build view information for prompt
        view_info_list = []
        total_row_count = 0
        
        if views_metadata and views_data:
            # Multiple views (includes dashboard sheets as view_id_sheet_N)
            for view_id in views_data:
                v_data = views_data.get(view_id)
                if not v_data:
                    continue
                v_metadata = views_metadata.get(view_id, {})
                view_name = v_metadata.get("name") or v_metadata.get("id") or view_id
                row_count = v_data.get("row_count", 0)
                total_row_count += row_count
                view_info_list.append({
                    "id": view_id,
                    "name": view_name,
                    "row_count": row_count
                })
        else:
            # Single view (backward compatibility)
            view_metadata = state.get("view_metadata") or {}
            view_data = state.get("view_data") or {}
            view_name = view_metadata.get("name") or view_metadata.get("id") or "Unknown View"
            row_count = view_data.get("row_count", 0)
            total_row_count = row_count
            view_info_list.append({
                "id": view_ids[0] if view_ids else "unknown",
                "name": view_name,
                "row_count": row_count
            })
        
        # Format view names for prompt
        if len(view_info_list) > 1:
            view_names = ", ".join([v["name"] for v in view_info_list])
            view_count_text = f"{len(view_info_list)} views"
        else:
            view_names = view_info_list[0]["name"] if view_info_list else "Unknown View"
            view_count_text = "1 view"
        
        summary_mode = state.get("summary_mode") or "full"
        v_data = views_data or {}
        if not v_data and state.get("view_data"):
            vd = state["view_data"]
            v_data = {"single": {"columns": vd.get("columns", []), "data": vd.get("data", []), "row_count": vd.get("row_count", 0)}}
        v_meta = views_metadata or {}
        if not v_meta and state.get("view_metadata"):
            v_meta = {"single": state.get("view_metadata", {})}
        view_data_str = _format_view_data(v_data, v_meta)
        prompt_vars = {
            "view_name": view_names,
            "row_count": total_row_count,
            "view_data": view_data_str,
            "insights": state.get("key_insights", []),
            "recommendations": state.get("recommendations", []),
            "user_query": state.get("user_query", "summarize this view")
        }
        if summary_mode == "brief":
            template_file = "agents/summary/final_summary_brief.txt"
            user_message = "Generate a 2-3 sentence executive summary."
        elif summary_mode == "custom":
            template_file = "agents/summary/final_summary_custom.txt"
            user_message = state.get("user_query", "summarize this view")
        else:
            template_file = "agents/summary/final_summary.txt"
            user_message = f"Generate executive summary and detailed analysis for {view_count_text}: {view_names}." if len(view_info_list) > 1 else "Generate executive summary and detailed analysis."
        
        system_prompt = prompt_registry.get_prompt(template_file, variables=prompt_vars)
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        summary_text = response.content.strip()
        
        return {
            **state,
            "executive_summary": summary_text,
            "detailed_analysis": summary_text,
            "final_answer": summary_text,
            "current_thought": None  # Clear thought as we're done
        }
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to generate summary: {str(e)}",
            "executive_summary": None,
            "detailed_analysis": None,
            "final_answer": "Summary generation failed. Please try again."
        }
