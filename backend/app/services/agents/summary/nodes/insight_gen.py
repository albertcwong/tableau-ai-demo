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
        view_metadata = state.get("view_metadata", {})
        view_name = view_metadata.get("name", view_metadata.get("id", "Unknown View"))
        row_count = state.get("view_data", {}).get("row_count", 0)
        
        # Build insight generation prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/summary/insight_generation.txt",
            variables={
                "view_name": view_name,
                "row_count": row_count,
                "column_stats": json.dumps(state.get("column_stats", {}), indent=2),
                "trends": json.dumps(state.get("trends", []), indent=2),
                "outliers": json.dumps(state.get("outliers", []), indent=2),
                "correlations": json.dumps(state.get("correlations", {}), indent=2)
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
            {"role": "user", "content": f"Generate insights for: {state.get('user_query', 'summarize this view')}"}
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
