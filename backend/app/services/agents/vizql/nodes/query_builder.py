"""Query builder node for constructing VizQL queries."""
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.agents.vizql.state import VizQLAgentState
from app.services.agents.vizql.context_builder import build_full_compressed_context
from app.services.agents.vizql.query_helpers import (
    detect_and_apply_date_functions,
    detect_and_apply_count_functions,
    detect_and_apply_context_filters,
    adjust_calculated_field_names,
)
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql", "query_builder")
async def build_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Construct VizQL Data Service query from intent and schema.
    
    This is an "Act" step in ReAct.
    """
    try:
        schema = state.get("schema")
        if not schema:
            return {
                **state,
                "error": "Schema not available. Cannot build query.",
                "query_draft": None
            }
        
        datasource_ids = state.get("context_datasources", [])
        if not datasource_ids:
            return {
                **state,
                "error": "No datasource ID available.",
                "query_draft": None
            }
        
        datasource_id = datasource_ids[0]
        
        # Check if we have enriched schema (from Phase 2)
        enriched_schema = state.get("enriched_schema")
        
        # Build compressed context if enriched schema is available
        if enriched_schema:
            logger.info("Using enriched schema with compressed context")
            compressed_context = build_full_compressed_context(
                enriched_schema=enriched_schema,
                user_query=state.get("user_query", ""),
                required_measures=state.get("required_measures", []),
                required_dimensions=state.get("required_dimensions", []),
                required_filters=state.get("required_filters", {}),
                topN=state.get("topN", {"enabled": False}),
                sorting=state.get("sorting", []),
                calculations=state.get("calculations", []),
                bins=state.get("bins", [])
            )
            
            # Split compressed context into components for prompt template
            context_lines = compressed_context.split("\n")
            compressed_schema_lines = []
            semantic_hints_lines = []
            field_lookup_lines = []
            parsed_intent_lines = []
            current_section = None
            
            for line in context_lines:
                if line.startswith("## Available Fields"):
                    current_section = "schema"
                    compressed_schema_lines.append(line)
                elif line.startswith("## Query Construction Hints"):
                    current_section = "hints"
                    semantic_hints_lines.append(line)
                elif line.startswith("## Field Matching Hints"):
                    current_section = "lookup"
                    field_lookup_lines.append(line)
                elif line.startswith("## Parsed Intent"):
                    current_section = "intent"
                    parsed_intent_lines.append(line)
                elif current_section == "schema":
                    compressed_schema_lines.append(line)
                elif current_section == "hints":
                    semantic_hints_lines.append(line)
                elif current_section == "lookup":
                    field_lookup_lines.append(line)
                elif current_section == "intent":
                    parsed_intent_lines.append(line)
            
            compressed_schema = "\n".join(compressed_schema_lines) if compressed_schema_lines else ""
            semantic_hints = "\n".join(semantic_hints_lines) if semantic_hints_lines else ""
            field_lookup_hints = "\n".join(field_lookup_lines) if field_lookup_lines else ""
            parsed_intent = "\n".join(parsed_intent_lines) if parsed_intent_lines else ""
            
            # Get query construction prompt with compressed context
            system_prompt = prompt_registry.get_prompt(
                "agents/vizql/query_construction.txt",
                variables={
                    "compressed_schema": compressed_schema,
                    "semantic_hints": semantic_hints,
                    "field_lookup_hints": field_lookup_hints,
                    "parsed_intent": parsed_intent,
                    "datasource_id": datasource_id
                }
            )
        else:
            # Fallback to basic schema format (backward compatibility)
            logger.info("Using basic schema (enrichment unavailable)")
            # Build parsed intent section even without enriched schema
            parsed_intent_parts = []
            if state.get("topN", {}).get("enabled"):
                topN = state.get("topN", {})
                parsed_intent_parts.append("## Parsed Intent")
                parsed_intent_parts.append("**CRITICAL: TOP N PATTERN DETECTED**")
                parsed_intent_parts.append(f"User wants top/bottom {topN.get('howMany', 'N')} {topN.get('dimensionField', 'dimension')} by {topN.get('measureField', 'measure')}")
                parsed_intent_parts.append(f"Direction: {topN.get('direction', 'TOP')}")
                parsed_intent_parts.append("**YOU MUST USE TOP FILTER, NOT SORTING!**")
            parsed_intent = "\n".join(parsed_intent_parts) if parsed_intent_parts else ""
            
            system_prompt = prompt_registry.get_prompt(
                "agents/vizql/query_construction.txt",
                variables={
                    "compressed_schema": f"## Available Fields\n{json.dumps(schema.get('columns', []), indent=2)}",
                    "semantic_hints": "## Query Construction Hints\nUsing basic schema. Field roles may not be available.",
                    "field_lookup_hints": "",
                    "parsed_intent": parsed_intent,
                    "datasource_id": datasource_id
                }
            )
        
        # Include few-shot examples
        examples = prompt_registry.get_examples("agents/vizql/examples.yaml")
        messages = prompt_registry.build_few_shot_prompt(
            system_prompt,
            examples,
            f"Build query for: {state['user_query']}"
        )
        
        # Initialize AI client
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        # Call AI
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        # Parse query JSON
        try:
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                # Find JSON block
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
            
            query_draft = json.loads(content)
            
            # Ensure query has required structure
            if "datasource" not in query_draft:
                query_draft["datasource"] = {"datasourceLuid": datasource_id}
            if "query" not in query_draft:
                query_draft["query"] = {}
            if "options" not in query_draft:
                query_draft["options"] = {
                    "returnFormat": "OBJECTS",
                    "disaggregate": False
                }
            
            # CRITICAL: Apply automatic date function detection and correction
            # This ensures date fields have proper temporal functions even if LLM missed them
            user_query = state.get("user_query", "")
            query_draft = detect_and_apply_date_functions(query_draft, user_query, enriched_schema)
            
            # CRITICAL: Apply automatic COUNTD detection for "how many" queries
            # This ensures count queries have COUNTD function even if LLM missed it
            query_draft = detect_and_apply_count_functions(query_draft, user_query, enriched_schema)
            
            # CRITICAL: Apply automatic context filter detection
            # This ensures hierarchical filter dependencies are properly handled
            query_draft = detect_and_apply_context_filters(query_draft, user_query)
            
            # CRITICAL: Adjust calculated field names to avoid conflicts with existing fields
            # This ensures calculated fields have unique names even if LLM missed the instruction
            query_draft = adjust_calculated_field_names(query_draft, enriched_schema, schema)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query JSON: {e}. Response: {response.content}")
            return {
                **state,
                "error": f"Failed to parse query JSON: {str(e)}",
                "query_draft": None
            }
        
        # Don't increment query_version here - it's incremented in refiner
        # Only increment on initial build (when query_version is 0 or missing)
        query_version = state.get("query_version", 0)
        if query_version == 0:
            query_version = 1
        
        return {
            **state,
            "query_draft": query_draft,
            "query_version": query_version,
            "current_thought": f"Built query version {query_version} with {len(query_draft.get('query', {}).get('fields', []))} fields"
        }
    except Exception as e:
        logger.error(f"Error building query: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to build query: {str(e)}",
            "query_draft": None
        }
