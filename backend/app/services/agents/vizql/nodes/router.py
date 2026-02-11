"""Router node for classifying user queries."""
import json
import logging
import re
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.agents.vizql.rule_based_router import get_rule_based_router
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)

# Configuration: Use rule-based router by default (faster, no LLM cost)
USE_RULE_BASED_ROUTER = True  # Set to False to use LLM-based router


@track_node_execution("vizql", "router")
async def route_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Classify user query to determine routing path.
    
    Uses fast rule-based router by default (< 1ms, no LLM cost).
    Can fall back to LLM-based router if USE_RULE_BASED_ROUTER = False.
    
    Classifications:
    - schema_query: Answerable from schema metadata
    - reformat_previous: Reformat previous query results
    - new_query: Requires new VizQL query
    """
    try:
        user_query = state.get("user_query", "")
        previous_results = state.get("previous_results")
        has_previous_results = previous_results is not None and len(previous_results.get("data", [])) > 0
        
        if USE_RULE_BASED_ROUTER:
            # Use fast rule-based router (no LLM, < 1ms)
            router = get_rule_based_router()
            query_type, reasoning, confidence = router.classify(
                user_query,
                has_previous_results
            )
            
            logger.info(f"Rule-based router: classified as '{query_type}' with confidence {confidence:.2f}: {reasoning}")
            
            return {
                **state,
                "query_type": query_type,
                "routing_reason": reasoning,
                "routing_confidence": confidence,
                "current_thought": f"Classified query as '{query_type}' ({reasoning})"
            }
        
        # Fall back to LLM-based router (slower, but potentially more accurate for edge cases)
        logger.info("Using LLM-based router (slower)")
        enriched_schema = state.get("enriched_schema")
        
        # Build context for routing prompt
        has_schema = enriched_schema is not None
        field_count = len(enriched_schema.get("fields", [])) if has_schema else 0
        measures_count = len(enriched_schema.get("measures", [])) if has_schema else 0
        dimensions_count = len(enriched_schema.get("dimensions", [])) if has_schema else 0
        
        previous_row_count = len(previous_results.get("data", [])) if has_previous_results else 0
        previous_columns = ", ".join(previous_results.get("columns", [])) if has_previous_results else ""
        
        # Get routing prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/routing.txt",
            variables={
                "user_query": user_query,
                "has_schema": has_schema,
                "field_count": field_count,
                "measures_count": measures_count,
                "dimensions_count": dimensions_count,
                "has_previous_results": has_previous_results,
                "previous_row_count": previous_row_count,
                "previous_columns": previous_columns
            }
        )
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL
        )
        
        # Call LLM to classify query
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Classify this query: {user_query}"}
        ]
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        # Parse classification
        try:
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            
            classification = json.loads(content)
            
            query_type = classification.get("query_type", "new_query")
            confidence = classification.get("confidence", 0.5)
            reasoning = classification.get("reasoning", "No reasoning provided")
            
            # Validate classification
            if query_type not in ["schema_query", "reformat_previous", "new_query"]:
                logger.warning(f"Invalid query type '{query_type}', defaulting to new_query")
                query_type = "new_query"
            
            # If classified as reformat_previous but no previous results, change to new_query
            if query_type == "reformat_previous" and not has_previous_results:
                logger.info("Query classified as reformat_previous but no previous results available, changing to new_query")
                query_type = "new_query"
                reasoning = "Changed from reformat_previous to new_query because no previous results available"
            
            logger.info(f"LLM router: classified as '{query_type}' with confidence {confidence:.2f}: {reasoning}")
            
            return {
                **state,
                "query_type": query_type,
                "routing_reason": reasoning,
                "routing_confidence": confidence,
                "current_thought": f"Classified query as '{query_type}' ({reasoning})"
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}. Response: {response.content}")
            # Default to new_query on parse error
            return {
                **state,
                "query_type": "new_query",
                "routing_reason": "Failed to classify, defaulting to new query",
                "routing_confidence": 0.5,
                "current_thought": "Classification failed, proceeding with new query"
            }
    
    except Exception as e:
        logger.error(f"Error in router node: {e}", exc_info=True)
        # Default to new_query on error
        return {
            **state,
            "query_type": "new_query",
            "routing_reason": f"Router error: {str(e)}",
            "routing_confidence": 0.0,
            "current_thought": "Router error, proceeding with new query"
        }
