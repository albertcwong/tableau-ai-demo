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
        
        # Validate API key is present
        if not api_key:
            logger.error("API key missing from state - cannot make gateway request")
            return {
                **state,
                "error": "Failed to plan query: Authorization header required for direct authentication",
                "required_measures": [],
                "required_dimensions": [],
                "required_filters": {}
            }
        
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
            messages=messages,
            api_key=api_key
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
        
        # Extract all pattern types
        topN = intent.get("topN", {"enabled": False})
        sorting = intent.get("sorting", [])
        calculations = intent.get("calculations", [])
        bins = intent.get("bins", [])
        filters = intent.get("filters", {})
        
        # Build thought message with pattern summary
        thought_parts = [
            f"{len(intent.get('measures', []))} measures",
            f"{len(intent.get('dimensions', []))} dimensions"
        ]
        if topN.get("enabled"):
            thought_parts.append(f"TOP {topN.get('howMany', 'N')} pattern")
        if filters:
            filter_types = [f.get("filterType", "UNKNOWN") for f in filters.values() if isinstance(f, dict)]
            if filter_types:
                thought_parts.append(f"Filters: {', '.join(set(filter_types))}")
        if calculations:
            thought_parts.append(f"{len(calculations)} calculation(s)")
        if bins:
            thought_parts.append(f"{len(bins)} bin(s)")
        if sorting:
            thought_parts.append(f"{len(sorting)} sort field(s)")
        
        return {
            **state,
            "required_measures": intent.get("measures", []),
            "required_dimensions": intent.get("dimensions", []),
            "required_filters": filters,
            "topN": topN,
            "sorting": sorting,
            "calculations": calculations,
            "bins": bins,
            "current_thought": f"Parsed intent: {', '.join(thought_parts)}",
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
            "required_filters": {},
            "topN": {"enabled": False},
            "sorting": [],
            "calculations": [],
            "bins": []
        }
