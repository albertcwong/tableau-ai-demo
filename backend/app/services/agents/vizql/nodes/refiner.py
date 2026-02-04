"""Refiner node for fixing query errors."""
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


@track_node_execution("vizql", "refiner")
async def refine_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Refine query based on validation errors.
    
    This is a "Reason" step in ReAct - reflect on errors and fix.
    """
    # Check max refinement attempts
    query_version = state.get("query_version", 0)
    if query_version >= 3:
        return {
            **state,
            "error": f"Max refinement attempts ({query_version}) reached. Errors: {state.get('validation_errors', [])}"
        }
    
    try:
        # Get refinement prompt
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/query_refinement.txt",
            variables={
                "original_query": json.dumps(state.get("query_draft", {}), indent=2),
                "errors": state.get("validation_errors", []),
                "suggestions": state.get("validation_suggestions", []),
                "schema": json.dumps(state.get("schema", {}).get("columns", []), indent=2)
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
            {"role": "user", "content": "Fix the query based on validation errors."}
        ]
        
        response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        # Parse corrected query
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
            
            corrected_query = json.loads(content)
            
            return {
                **state,
                "query_draft": corrected_query,
                "current_thought": f"Refined query (attempt {query_version + 1}) based on {len(state.get('validation_errors', []))} errors"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse refined query JSON: {e}")
            return {
                **state,
                "error": f"Failed to parse refined query: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Error refining query: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to refine query: {str(e)}"
        }
