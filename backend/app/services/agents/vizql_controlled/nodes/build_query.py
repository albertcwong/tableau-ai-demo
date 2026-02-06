"""Build query node - use LLM to generate VizQL query."""
import json
import logging
import re
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings

logger = logging.getLogger(__name__)


async def build_query_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Use LLM to generate VizQL query from user question.
    
    Operations:
    1. Load prompt template
    2. Format with schema, stats, user query, and error context (if retry)
    3. Call LLM with structured output
    4. Parse VizQL query JSON
    
    Duration: 2000-5000ms
    """
    user_query = state.get("user_query", "")
    schema = state.get("schema", {})
    metadata_stats = state.get("metadata_stats", {})
    datasource_id = state.get("datasource_id", "")
    attempt = state.get("attempt", 1)
    validation_errors = state.get("validation_errors", [])
    execution_errors = state.get("execution_errors", [])
    
    if not schema:
        return {
            **state,
            "build_error": "Schema not available",
            "current_thought": "Error: Schema not available"
        }
    
    # Build error context if retry
    error_context = ""
    if attempt > 1:
        error_parts = []
        if validation_errors:
            error_parts.append(f"Previous Attempt Failed - Validation Errors:\n" + "\n".join(f"- {e}" for e in validation_errors))
        if execution_errors:
            error_parts.append(f"Previous Attempt Failed - Execution Errors:\n" + "\n".join(f"- {e}" for e in execution_errors))
        if error_parts:
            error_context = "\n\n## Previous Attempt Failed\n" + "\n".join(error_parts) + "\n\nFix these issues in your next query."
    
    # Format schema and stats for prompt
    schema_str = json.dumps(schema, indent=2)
    stats_str = json.dumps(metadata_stats, indent=2)
    
    # Get prompt template
    try:
        prompt_template = prompt_registry.get_prompt("agents/vizql_controlled/build_query.txt")
    except Exception as e:
        logger.warning(f"Prompt not found, using fallback: {e}")
        prompt_template = """You are a VizQL query builder. Generate a valid VizQL query JSON.

Schema: {schema}
Statistics: {metadata_stats}
User Question: {user_query}
{error_context}

Output JSON:
{{
  "query": {{...}},
  "reasoning": "..."
}}"""
    
    # Format prompt
    system_prompt = prompt_template.format(
        schema=schema_str,
        metadata_stats=stats_str,
        user_query=user_query,
        error_context=error_context,
        datasource_id=datasource_id
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Build a VizQL query for: {user_query}"}
    ]
    
    # Get API key and model from state
    api_key = state.get("api_key")
    model = state.get("model") or settings.DEFAULT_LLM_MODEL
    
    if not api_key:
        return {
            **state,
            "build_error": "API key required for LLM calls",
            "current_thought": "Error: Missing API key"
        }
    
    logger.info(f"Building query (attempt {attempt}) using model: {model}")
    
    try:
        # Call LLM
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
        response = await ai_client.chat(
            model=model,
            messages=messages
        )
        
        content = response.content or ""
        
        # Parse JSON from response
        # Try to extract JSON block first
        json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object in response
            json_match = re.search(r'\{.*"query".*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content
        
        # Parse JSON
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON, retrying: {e}")
            # Retry parse once
            try:
                # Try to fix common issues
                json_str = json_str.strip()
                if not json_str.startswith("{"):
                    # Find first {
                    start_idx = json_str.find("{")
                    if start_idx >= 0:
                        json_str = json_str[start_idx:]
                result = json.loads(json_str)
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse JSON after retry: {e2}")
                return {
                    **state,
                    "build_error": f"Failed to parse LLM response as JSON: {str(e2)}",
                    "current_thought": "Error: Invalid JSON response from LLM"
                }
        
        query_draft = result.get("query")
        reasoning = result.get("reasoning", "")
        
        if not query_draft:
            return {
                **state,
                "build_error": "LLM response missing 'query' field",
                "current_thought": "Error: Invalid response format"
            }
        
        # Ensure query_draft has the full structure with datasource, query, and options
        # The LLM should return the full query object, but handle cases where it doesn't
        if isinstance(query_draft, dict):
            # Check if it already has the full structure
            if "datasource" in query_draft and "query" in query_draft:
                # Already has full structure, just ensure options
                if "options" not in query_draft:
                    query_draft["options"] = {
                        "returnFormat": "OBJECTS",
                        "disaggregate": False
                    }
                # Ensure datasource has datasourceLuid
                if "datasourceLuid" not in query_draft.get("datasource", {}):
                    query_draft["datasource"] = {"datasourceLuid": datasource_id}
            elif "fields" in query_draft or "filters" in query_draft:
                # LLM returned just the inner query object, wrap it
                query_draft = {
                    "datasource": {
                        "datasourceLuid": datasource_id
                    },
                    "query": query_draft,
                    "options": {
                        "returnFormat": "OBJECTS",
                        "disaggregate": False
                    }
                }
            else:
                # Unknown structure, try to wrap it
                query_draft = {
                    "datasource": {
                        "datasourceLuid": datasource_id
                    },
                    "query": query_draft,
                    "options": {
                        "returnFormat": "OBJECTS",
                        "disaggregate": False
                    }
                }
        else:
            return {
                **state,
                "build_error": f"Invalid query format: expected dict, got {type(query_draft)}",
                "current_thought": "Error: Invalid query format"
            }
        
        # Final validation: ensure required fields exist
        if not query_draft.get("datasource", {}).get("datasourceLuid"):
            query_draft["datasource"] = {"datasourceLuid": datasource_id}
        
        if "query" not in query_draft:
            return {
                **state,
                "build_error": "Query missing 'query' section",
                "current_thought": "Error: Invalid query structure"
            }
        
        if "options" not in query_draft:
            query_draft["options"] = {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        
        logger.info(f"Query built successfully (attempt {attempt})")
        
        return {
            **state,
            "query_draft": query_draft,
            "reasoning": reasoning,
            "current_thought": "Building VizQL query..."
        }
        
    except Exception as e:
        error_msg = f"Failed to build query: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "build_error": error_msg,
            "current_thought": f"Error: {error_msg}"
        }