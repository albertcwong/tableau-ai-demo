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
        view_metadata = state.get("view_metadata", {})
        view_name = view_metadata.get("name", view_metadata.get("id", "Unknown View"))
        row_count = state.get("view_data", {}).get("row_count", 0)
        
        # Build comprehensive summary prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/summary/final_summary.txt",
            variables={
                "view_name": view_name,
                "row_count": row_count,
                "insights": state.get("key_insights", []),
                "recommendations": state.get("recommendations", []),
                "user_query": state.get("user_query", "summarize this view")
            }
        )
        
        # Initialize AI client with API key from state
        api_key = state.get("api_key")
        model = state.get("model", "gpt-4")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate executive summary and detailed analysis."}
        ]
        
        response = await ai_client.chat(
            model=model,
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
