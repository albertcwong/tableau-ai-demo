"""Insight generation node for creating key insights."""
import json
import logging
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


async def generate_insights_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Use AI to generate key insights from analysis.
    
    This is a "Reason" step in ReAct - extract meaningful insights.
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
        
        # Build insight generation prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/summary/insight_generation.txt",
            variables={
                "view_name": view_names,  # Can be multiple views
                "row_count": total_row_count,
                "column_stats": json.dumps(state.get("column_stats", {}), indent=2),
                "trends": json.dumps(state.get("trends", []), indent=2),
                "outliers": json.dumps(state.get("outliers", []), indent=2),
                "correlations": json.dumps(state.get("correlations", {}), indent=2)
            }
        )
        
        # Update user message to mention multiple views if applicable
        user_query = state.get('user_query', 'summarize this view')
        if len(view_info_list) > 1:
            user_query = f"{user_query} (analyzing {view_count_text}: {view_names})"
        
        # Initialize AI client with API key from state
        api_key = state.get("api_key")
        model = state.get("model", "gpt-4")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate insights for: {user_query}"}
        ]
        
        response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        # Parse insights (expects JSON with insights and recommendations)
        try:
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                json_start = None
                json_end = None
                for i, line in enumerate(lines):
                    if "```json" in line.lower() or "```" in line:
                        if json_start is None:
                            json_start = i + 1
                        else:
                            json_end = i
                            break
                if json_start and json_end:
                    content = "\n".join(lines[json_start:json_end])
                elif json_start:
                    content = "\n".join(lines[json_start:-1])
            
            result = json.loads(content)
            
            return {
                **state,
                "key_insights": result.get("insights", []),
                "recommendations": result.get("recommendations", []),
                "current_thought": f"Generated {len(result.get('insights', []))} insights and {len(result.get('recommendations', []))} recommendations"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse insights JSON: {e}. Response: {response.content}")
            # Fallback: extract insights from text
            insights = [response.content[:500]]  # Use first 500 chars as insight
            return {
                **state,
                "key_insights": insights,
                "recommendations": [],
                "current_thought": "Generated insights (fallback mode)"
            }
    except Exception as e:
        logger.error(f"Error generating insights: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to generate insights: {str(e)}",
            "key_insights": [],
            "recommendations": []
        }
