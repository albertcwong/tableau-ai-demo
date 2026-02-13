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
    # query_version starts at 1, so max_retries means we can have versions 1 through max_retries
    # After max_retries refinements, query_version will be max_retries + 1, so stop
    max_retries = settings.VIZQL_MAX_RETRIES
    query_version = state.get("query_version", 0)
    if query_version >= max_retries + 1:
        return {
            **state,
            "error": f"Max refinement attempts ({max_retries}) reached. Errors: {state.get('validation_errors', [])}"
        }
    
    try:
        # Get enriched schema if available for better refinement
        enriched_schema = state.get("enriched_schema")
        schema_data = state.get("schema", {})
        
        # Use enriched schema for refinement if available
        if enriched_schema:
            from app.services.agents.vizql.context_builder import build_compressed_schema_context
            schema_context = build_compressed_schema_context(enriched_schema)
        else:
            schema_context = json.dumps(schema_data.get("columns", []), indent=2)
        
        # Get refinement prompt with enhanced suggestions
        validation_errors = state.get("validation_errors", [])
        validation_suggestions = state.get("validation_suggestions", [])
        
        # Check for execution errors (from Tableau API)
        execution_error = state.get("execution_error")
        tableau_error_message = state.get("tableau_error_message")
        execution_error_query = state.get("execution_error_query")
        
        # If we have an execution error, use the failed query as the original query
        # and add the Tableau error to the errors list
        original_query = state.get("query_draft", {})
        if execution_error_query:
            original_query = execution_error_query
            logger.info(f"Using execution_error_query as original_query for refinement")
        
        # Combine validation errors with execution errors
        all_errors = list(validation_errors) if isinstance(validation_errors, list) else []
        if execution_error:
            error_msg = f"Query execution failed: {execution_error}"
            if tableau_error_message and tableau_error_message != execution_error:
                error_msg += f"\n\nTableau Server Error Details:\n{tableau_error_message}"
            all_errors.append(error_msg)
        
        # Ensure errors and suggestions are lists (not None or empty)
        if not isinstance(all_errors, list):
            all_errors = []
        if not isinstance(validation_suggestions, list):
            validation_suggestions = []
        
        # Log what we're sending to LLM for debugging
        logger.info(
            f"Refining query (attempt {query_version + 1}) with "
            f"{len(all_errors)} total errors ({len(validation_errors)} validation, {1 if execution_error else 0} execution) "
            f"and {len(validation_suggestions)} suggestions"
        )
        if all_errors:
            logger.info(f"All errors: {all_errors}")
        if validation_suggestions:
            logger.info(f"Validation suggestions: {validation_suggestions}")
        if tableau_error_message:
            logger.info(f"Tableau error message: {tableau_error_message[:200]}...")
        
        system_prompt = prompt_registry.get_prompt(
            "agents/vizql/query_refinement.txt",
            variables={
                "original_query": json.dumps(original_query, indent=2),
                "errors": all_errors,  # Pass combined errors as list for template to loop
                "suggestions": validation_suggestions,  # Pass as list for template to loop
                "schema": schema_context,
                "user_query": state.get("user_query", ""),
                "has_execution_error": bool(execution_error),
                "tableau_error": tableau_error_message or ""
            }
        )
        
        # Log the rendered prompt (first 1000 chars) to verify errors/suggestions are included
        logger.debug(f"Refinement prompt preview: {system_prompt[:1000]}...")
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        # Build user message with explicit instruction
        user_message = "Fix the query based on the errors and suggestions provided above. Apply ALL fixes."
        if all_errors:
            user_message += f"\n\nThere are {len(all_errors)} error(s) to fix."
            if execution_error:
                user_message += "\n\n⚠️ CRITICAL: This query failed when executed against Tableau Server. Check the Tableau Server Error Details above to understand what went wrong."
        if validation_suggestions:
            user_message += f"\n\nThere are {len(validation_suggestions)} suggestion(s) to follow."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Log the full prompt being sent (for debugging)
        logger.info(
            f"Sending refinement request to LLM:\n"
            f"  Errors: {len(validation_errors)}\n"
            f"  Suggestions: {len(validation_suggestions)}\n"
            f"  Prompt length: {len(system_prompt)} chars"
        )
        if validation_errors:
            logger.info(f"  Error details: {validation_errors}")
        if validation_suggestions:
            logger.info(f"  Suggestion details: {validation_suggestions[:3]}...")  # First 3 suggestions
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
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
            
            # Increment query_version to track refinement attempts
            new_query_version = query_version + 1
            
            return {
                **state,
                "query_draft": corrected_query,
                "query_version": new_query_version,
                "current_thought": f"Refined query (attempt {new_query_version}) based on {len(state.get('validation_errors', []))} errors"
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
