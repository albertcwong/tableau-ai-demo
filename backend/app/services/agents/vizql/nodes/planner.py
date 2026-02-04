"""Planner node for parsing user intent."""
import json
import logging
from typing import Dict, Any
# Note: Using dict format for messages to match UnifiedAIClient API

from app.services.agents.vizql.state import VizQLAgentState
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql", "planner")
async def plan_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Parse user intent to identify required measures, dimensions, and filters.
    
    This is the "Reason" step in ReAct.
    """
    try:
        # Get planning prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/planning.txt",
            variables={
                "user_query": state["user_query"]
            }
        )
        
        # Initialize AI client with API key from state
        api_key = state.get("api_key")
        model = state.get("model", "gpt-4")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        
        # Call LLM to parse intent
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["user_query"]}
        ]
        
        response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        # Parse response (expects JSON with measures, dimensions, filters)
        try:
            # Try to extract JSON from response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            
            intent = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent JSON: {e}. Response: {response.content}")
            # Fallback: extract basic intent
            intent = {
                "measures": [],
                "dimensions": [],
                "filters": {},
                "aggregation": "sum"
            }
        
        return {
            **state,
            "required_measures": intent.get("measures", []),
            "required_dimensions": intent.get("dimensions", []),
            "required_filters": intent.get("filters", {}),
            "current_thought": f"Parsed intent: {len(intent.get('measures', []))} measures, {len(intent.get('dimensions', []))} dimensions",
            "messages": list(state.get("messages", [])) + [
                {"role": "user", "content": state["user_query"]},
                {"role": "assistant", "content": f"Intent parsed: {json.dumps(intent, indent=2)}"}
            ]
        }
    except Exception as e:
        logger.error(f"Error in planner node: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to parse query intent: {str(e)}",
            "required_measures": [],
            "required_dimensions": [],
            "required_filters": {}
        }
