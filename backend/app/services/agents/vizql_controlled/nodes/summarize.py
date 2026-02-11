"""Summarize node - format results into natural language + extract context."""
import json
import logging
import re
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings

logger = logging.getLogger(__name__)


async def summarize_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Format results into natural language + extract context.
    
    Operations:
    1. Call LLM to format data
    2. Parse response for natural language + context
    3. Extract `shown_entities` from LLM output
    
    Duration: 2000-5000ms
    """
    user_query = state.get("user_query", "")
    raw_data = state.get("raw_data")
    
    if not raw_data:
        return {
            **state,
            "final_answer": "I wasn't able to retrieve the data needed to answer your question.",
            "current_thought": "Error: No data available to summarize"
        }
    
    # Format raw data for LLM
    data_str = json.dumps(raw_data, indent=2)
    
    # Get prompt template
    try:
        prompt_template = prompt_registry.get_prompt("agents/vizql_controlled/summarize.txt")
    except Exception as e:
        logger.warning(f"Prompt not found, using fallback: {e}")
        prompt_template = """Format this data into a clear response.

User Question: {user_query}

Raw Data:
```json
{raw_data}
```

After your response, include:
---CONTEXT---
{{
  "shown_entities": {{...}}
}}"""
    
    system_prompt = prompt_template.format(
        user_query=user_query,
        raw_data=data_str
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Format the data for: {user_query}"}
    ]
    
    # Get model and provider from state
    model = state.get("model") or settings.DEFAULT_LLM_MODEL
    provider = state.get("provider", "openai")
    
    logger.info(f"Summarizing results using model: {model}, provider: {provider}")
    
    try:
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
                    json_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', context_part, re.DOTALL)
                    if json_match:
                        context_json = json.loads(json_match.group(1))
                    else:
                        # Try parsing the whole context part as JSON
                        context_json = json.loads(context_part)
                    
                    shown_entities = context_json.get("shown_entities", {})
                    logger.info(f"Extracted shown_entities: {len(shown_entities)} dimensions")
                except Exception as e:
                    logger.warning(f"Failed to parse shown_entities context: {e}")
        
        logger.info(f"Summarize node complete: {len(final_answer)} chars, {len(shown_entities)} dimensions tracked")
        
        return {
            **state,
            "final_answer": final_answer,
            "shown_entities": shown_entities,
            "current_thought": "Generating response..."
        }
        
    except Exception as e:
        error_msg = f"Failed to summarize: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "final_answer": f"I encountered an error while formatting the response: {str(e)}",
            "current_thought": f"Error: {error_msg}"
        }