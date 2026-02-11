"""Summarize data node - formats raw data into natural language response."""
import json
import logging
from typing import Dict, Any

from app.services.agents.vizql_tool_use.state import VizQLToolUseState
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings

logger = logging.getLogger(__name__)


async def summarize_node(state: VizQLToolUseState) -> Dict[str, Any]:
    """
    Step 2: Format raw data into natural language response.
    
    This node:
    1. Takes raw data from get_data step
    2. Calls LLM to format it appropriately
    3. Returns final answer
    """
    try:
        user_query = state.get("user_query", "")
        raw_data = state.get("raw_data")
        
        logger.info(f"Summarize node: formatting data for query='{user_query}'")
        logger.info(f"Raw data type: {type(raw_data)}, value: {str(raw_data)[:200] if raw_data else 'None'}")
        
        # Set current_thought for reasoning steps UI
        current_thought = "Formatting data into natural language response"
        
        if not raw_data:
            logger.warning("No raw data available to summarize")
            # Check if there's an error in state
            error = state.get("error")
            if error:
                return {
                    **state,
                    "current_thought": "Error: No data available to summarize",
                    "final_answer": f"I encountered an error while retrieving data: {error}"
                }
            return {
                **state,
                "current_thought": "Error: No data available to summarize",
                "final_answer": "I wasn't able to retrieve the data needed to answer your question."
            }
        
        # Get prompt
        system_prompt = prompt_registry.get_prompt("agents/vizql_tool_use/summarize.txt")
        
        # Format raw data for LLM
        data_str = json.dumps(raw_data, indent=2)
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""User Question: {user_query}

Raw Data:
```json
{data_str}
```

Please format this data into a clear, natural language response that answers the user's question."""}
        ]
        
        # Get model and provider from state
        model = state.get("model")
        provider = state.get("provider", "openai")
        if not model:
            try:
                model = settings.DEFAULT_LLM_MODEL
            except AttributeError:
                model = "gpt-4"  # Default fallback
        
        logger.info(f"Summarize using model: {model}, provider: {provider}")
        
        # Call LLM
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL
        )
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        full_response = response.content or ""
        
        # Parse response to extract shown_entities context
        shown_entities = {}
        final_answer = full_response
        
        # Check if response contains ---CONTEXT--- marker
        if "---CONTEXT---" in full_response:
            parts = full_response.split("---CONTEXT---")
            final_answer = parts[0].strip()
            
            if len(parts) > 1:
                context_part = parts[1].strip()
                # Try to parse JSON from context part
                try:
                    # Extract JSON block (might be in code fence or raw)
                    import re
                    json_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', context_part)
                    if json_match:
                        context_json = json.loads(json_match.group(1))
                    else:
                        # Try parsing the whole context part as JSON
                        context_json = json.loads(context_part)
                    
                    shown_entities = context_json.get("shown_entities", {})
                    logger.info(f"Extracted shown_entities: {len(shown_entities)} dimensions")
                    for dim_name, values in shown_entities.items():
                        logger.info(f"  - {dim_name}: {len(values)} values")
                except Exception as e:
                    logger.warning(f"Failed to parse shown_entities context: {e}")
                    # Continue without shown_entities - fallback will handle it
        
        logger.info(f"Summarize node complete: {len(final_answer)} chars, {len(shown_entities)} dimensions tracked")
        
        return {
            **state,
            "current_thought": current_thought,
            "final_answer": final_answer,
            "shown_entities": shown_entities  # Add to state for extraction
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_node: {e}", exc_info=True)
        return {
            **state,
            "current_thought": f"Error: {str(e)[:100]}",
            "error": str(e),
            "final_answer": f"I encountered an error while formatting the response: {str(e)}"
        }
