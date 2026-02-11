"""Summarizer node for generating final summary."""
import logging
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState
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
            # Multiple views
            for view_id in view_ids:
                v_metadata = views_metadata.get(view_id, {})
                v_data = views_data.get(view_id, {})
                view_name = v_metadata.get("name") or v_metadata.get("id") or view_id
                row_count = v_data.get("row_count", 0) if v_data else 0
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
        
        # Build comprehensive summary prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/summary/final_summary.txt",
            variables={
                "view_name": view_names,  # Can be multiple views
                "row_count": total_row_count,
                "insights": state.get("key_insights", []),
                "recommendations": state.get("recommendations", []),
                "user_query": state.get("user_query", "summarize this view")
            }
        )
        
        # Update user message to mention multiple views if applicable
        user_query = state.get("user_query", "summarize this view")
        if len(view_info_list) > 1:
            user_message = f"Generate executive summary and detailed analysis for {view_count_text}: {view_names}."
        else:
            user_message = "Generate executive summary and detailed analysis."
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL
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
