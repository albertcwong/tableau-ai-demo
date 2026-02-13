"""Enhanced query builder node with tool integration."""
import copy
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.runnables.config import ensure_config

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.agents.vizql_streamlined.tools import (
    get_datasource_schema,
    get_datasource_metadata,
    get_prior_query
)
from app.services.agents.vizql.context_builder import build_full_compressed_context
from app.services.agents.vizql.query_helpers import (
    detect_and_apply_date_functions,
    detect_and_apply_count_functions,
    detect_and_apply_context_filters,
    adjust_calculated_field_names,
    remove_fieldcaption_from_calculated_filters,
    validate_and_correct_filter_values,
)
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


def _create_tool_functions(datasource_id: str, site_id: Optional[str], message_history: List[Dict]) -> List[Dict]:
    """Create tool function definitions for LLM."""
    return [
        {
            "name": "get_datasource_schema",
            "description": "Fetch datasource schema (columns, measures, dimensions). Use this if schema is not provided in state or you need fresh schema data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datasource_id": {
                        "type": "string",
                        "description": "Datasource LUID"
                    },
                    "use_enriched": {
                        "type": "boolean",
                        "description": "Whether to use enriched schema with semantic metadata",
                        "default": True
                    }
                },
                "required": ["datasource_id"]
            }
        },
        {
            "name": "get_datasource_metadata",
            "description": "Fetch datasource metadata via REST API (name, project, tags, certification). Use this when you need datasource context or description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datasource_id": {
                        "type": "string",
                        "description": "Datasource LUID"
                    },
                    "site_id": {
                        "type": "string",
                        "description": "Site ID (optional)"
                    }
                },
                "required": ["datasource_id"]
            }
        },
        {
            "name": "get_prior_query",
            "description": "Search conversation history for similar queries. Use this when user query is similar to a prior message - you can reuse and modify the prior query instead of building from scratch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_query": {
                        "type": "string",
                        "description": "Current user query"
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "Similarity threshold (0.0-1.0), default 0.8",
                        "default": 0.8
                    }
                },
                "required": ["current_query"]
            }
        }
    ]


async def _execute_tool_call(tool_name: str, args: Dict[str, Any], state: StreamlinedVizQLState, tableau_client=None) -> Dict[str, Any]:
    """Execute a tool call."""
    datasource_id = state.get("context_datasources", [None])[0]
    site_id = state.get("site_id")
    message_history = state.get("messages", [])
    
    try:
        if tool_name == "get_datasource_schema":
            schema_result = await get_datasource_schema(
                datasource_id=args.get("datasource_id", datasource_id),
                site_id=args.get("site_id", site_id),
                use_enriched=args.get("use_enriched", True),
                tableau_client=tableau_client
            )
            return {"success": True, "result": schema_result}
        
        elif tool_name == "get_datasource_metadata":
            metadata_result = await get_datasource_metadata(
                datasource_id=args.get("datasource_id", datasource_id),
                site_id=args.get("site_id", site_id),
                tableau_client=tableau_client
            )
            return {"success": True, "result": metadata_result}
        
        elif tool_name == "get_prior_query":
            prior_query_result = get_prior_query(
                message_history=message_history,
                current_query=args.get("current_query", state.get("user_query", "")),
                similarity_threshold=args.get("similarity_threshold", 0.8)
            )
            return {"success": True, "result": prior_query_result}
        
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@track_node_execution("vizql_streamlined", "query_builder")
async def build_query_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Intelligently construct VizQL query with tool support.
    
    This node can:
    - Reuse queries from conversation history
    - Fetch schema only if needed
    - Fetch datasource metadata for context
    - Make intelligent decisions about what information is needed
    """
    try:
        datasource_ids = state.get("context_datasources", [])
        build_attempt = state.get("build_attempt", 1)
        execution_attempt = state.get("execution_attempt", 1)
        if not datasource_ids:
            reasoning_steps = state.get("reasoning_steps", [])
            reasoning_steps.append({
                "node": "build_query",
                "timestamp": datetime.utcnow().isoformat(),
                "action": "error",
                "error": "No datasource ID available."
            })
            return {
                **state,
                "error": "No datasource ID available.",
                "query_draft": None,
                "build_attempt": build_attempt,
                "execution_attempt": execution_attempt,
                "reasoning_steps": reasoning_steps,
                "current_thought": f"Build attempt {build_attempt} failed: No datasource ID available.",
                "step_metadata": {
                    "build_attempt": build_attempt,
                    "query_draft": None
                }
            }
        
        datasource_id = datasource_ids[0]
        user_query = state.get("user_query", "")
        message_history = state.get("messages", [])
        enriched_schema = state.get("enriched_schema")
        schema = state.get("schema")
        validation_errors = state.get("validation_errors", [])
        build_errors = state.get("build_errors", [])
        execution_errors = state.get("execution_errors", [])
        
        # If we're retrying after execution failure, reset build_attempt to start fresh
        # and increment execution_attempt
        # IMPORTANT: Also clear the error field so validation routing works correctly
        should_clear_error = False
        if execution_errors and not validation_errors and not build_errors:
            build_attempt = 1  # Reset build retry count for fresh build attempt
            execution_attempt = state.get("execution_attempt", 1) + 1
            should_clear_error = True  # Clear error from previous execution
        else:
            execution_attempt = state.get("execution_attempt", 1)
        
        # Increment build_attempt if this is a retry due to validation/build errors
        if validation_errors or build_errors:
            build_attempt = build_attempt + 1
        
        # Initialize reasoning steps
        reasoning_steps = state.get("reasoning_steps", [])
        reasoning_steps.append({
            "node": "build_query",
            "timestamp": datetime.utcnow().isoformat(),
            "thought": f"Building query for: {user_query}",
            "build_attempt": build_attempt
        })
        
        # Get model and provider
        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        
        # Step 1: Extract context from conversation history
        prior_query_result = None
        context_fields = []  # Fields from previous queries
        context_measures = []  # Measures from previous queries
        context_dimensions = []  # Dimensions from previous queries
        
        if message_history:
            # Check for similar queries (for reuse)
            prior_query_result = get_prior_query(
                message_history=message_history,
                current_query=user_query,
                similarity_threshold=0.8
            )
            
            # Also extract fields from most recent assistant message (even if not similar)
            # This handles cases like "break it down by region" after "show me sales"
            user_query_lower = user_query.lower()
            reference_keywords = ["break", "break down", "break it down", "by", "for each", "those", "that", "it", "them", "group"]
            has_reference = any(keyword in user_query_lower for keyword in reference_keywords)
            
            if has_reference:
                # Look for most recent assistant message with a query
                for msg in reversed(message_history):
                    if msg.get("role") == "assistant":
                        query_draft = msg.get("query_draft")
                        if query_draft and isinstance(query_draft, dict):
                            prev_fields = query_draft.get("query", {}).get("fields", [])
                            for field in prev_fields:
                                field_caption = field.get("fieldCaption", "")
                                if field_caption:
                                    # Determine if measure or dimension based on function presence
                                    if field.get("function"):
                                        if field_caption not in context_measures:
                                            context_measures.append(field_caption)
                                    else:
                                        if field_caption not in context_dimensions:
                                            context_dimensions.append(field_caption)
                                    if field_caption not in context_fields:
                                        context_fields.append(field_caption)
                            logger.info(
                                f"Extracted context fields from previous query: "
                                f"{len(context_fields)} fields ({len(context_measures)} measures, {len(context_dimensions)} dimensions)"
                            )
                            break
        
        # Step 2: Determine if we need to fetch schema
        needs_schema = not schema and not enriched_schema
        
        # CRITICAL: Ensure we have schema before building query
        # Without schema, LLM cannot know which fields are available
        if needs_schema:
            logger.info("Schema not available - fetching before building query")
            try:
                config = ensure_config()
                tableau_client = config.get("configurable", {}).get("tableau_client")
                schema_result = await get_datasource_schema(
                    datasource_id=datasource_id,
                    site_id=state.get("site_id"),
                    use_enriched=True,
                    tableau_client=tableau_client
                )
                if schema_result and not schema_result.get("error"):
                    schema = {
                        "columns": schema_result.get("columns", [])
                    }
                    if schema_result.get("enriched"):
                        # Use the full enriched schema structure (includes fields array)
                        enriched_schema = {
                            "fields": schema_result.get("fields", []),  # Full field objects
                            "measures": schema_result.get("measures", []),
                            "dimensions": schema_result.get("dimensions", []),
                            "field_map": schema_result.get("field_map", {}),
                            "datasource_id": schema_result.get("datasource_id")
                        }
                    reasoning_steps.append({
                        "node": "build_query",
                        "timestamp": datetime.utcnow().isoformat(),
                        "action": "tool_call",
                        "tool": "get_datasource_schema",
                        "result": "success",
                        "fields_count": len(schema_result.get("columns", []))
                    })
                    logger.info(f"Fetched schema with {len(schema.get('columns', []))} columns")
                else:
                    error_msg = f"Failed to fetch schema: {schema_result.get('error', 'Unknown error')}"
                    logger.error(error_msg)
                    return {
                        **state,
                        "error": error_msg,
                        "query_draft": None,
                        "reasoning_steps": reasoning_steps
                    }
            except Exception as e:
                logger.error(f"Error fetching schema: {e}", exc_info=True)
                return {
                    **state,
                    "error": f"Failed to fetch schema: {str(e)}",
                    "query_draft": None,
                    "reasoning_steps": reasoning_steps
                }
        
        # Final check: ensure we have schema
        if not schema and not enriched_schema:
            error_msg = "Cannot build query without schema. Schema fetch failed or returned empty."
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "query_draft": None,
                "reasoning_steps": reasoning_steps
            }
        
        # Step 3: Build prompt with available context
        # If we have enriched schema, use compressed context
        if enriched_schema:
            field_count = len(enriched_schema.get("fields", []))
            measure_count = len(enriched_schema.get("measures", []))
            dimension_count = len(enriched_schema.get("dimensions", []))
            logger.info(
                f"Using enriched schema with compressed context: "
                f"{field_count} fields ({measure_count} measures, {dimension_count} dimensions)"
            )
            # Only pass intent parsing results if they're actually set and relevant
            # Since we removed the planner node, these should be empty unless explicitly set
            # Don't pass calculations/bins unless user explicitly requested them
            required_measures = state.get("required_measures", [])
            required_dimensions = state.get("required_dimensions", [])
            required_filters = state.get("required_filters", {})
            topN = state.get("topN", {"enabled": False})
            sorting = state.get("sorting", [])
            calculations = state.get("calculations", [])
            bins = state.get("bins", [])
            
            # CRITICAL: Only include calculations/bins if user explicitly mentioned them in query
            # Check if user query mentions calculation-related terms
            user_query_lower = user_query.lower()
            calculation_keywords = ["calculate", "calculation", "formula", "ratio", "margin", "percentage", "divide", "divided by"]
            bin_keywords = ["bin", "bins", "bucket", "buckets", "group by range"]
            
            # Filter out calculations/bins that weren't explicitly requested
            if calculations:
                # Only keep calculations if user query mentions calculation-related terms
                if not any(keyword in user_query_lower for keyword in calculation_keywords):
                    logger.info(f"Ignoring {len(calculations)} calculations from state - not mentioned in user query")
                    calculations = []
            
            if bins:
                # Only keep bins if user query mentions bin-related terms
                if not any(keyword in user_query_lower for keyword in bin_keywords):
                    logger.info(f"Ignoring {len(bins)} bins from state - not mentioned in user query")
                    bins = []
            
            compressed_context = build_full_compressed_context(
                enriched_schema=enriched_schema,
                user_query=user_query,
                required_measures=required_measures if required_measures else None,
                required_dimensions=required_dimensions if required_dimensions else None,
                required_filters=required_filters if required_filters else None,
                topN=topN if topN.get("enabled") else None,
                sorting=sorting if sorting else None,
                calculations=calculations if calculations else None,
                bins=bins if bins else None
            )
            
            # Split compressed context
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
        elif schema:
            # Use basic schema
            column_count = len(schema.get("columns", []))
            logger.info(f"Using basic schema with {column_count} columns")
            system_prompt = prompt_registry.get_prompt(
                "agents/vizql/query_construction.txt",
                variables={
                    "compressed_schema": f"## Available Fields\n{json.dumps(schema.get('columns', []), indent=2)}",
                    "semantic_hints": "## Query Construction Hints\nUsing basic schema. Field roles may not be available.",
                    "field_lookup_hints": "",
                    "parsed_intent": "",
                    "datasource_id": datasource_id
                }
            )
        else:
            # This should not happen - schema should be fetched above
            error_msg = "Schema not available after fetch attempt. Cannot build query."
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "query_draft": None,
                "reasoning_steps": reasoning_steps
            }
        
        # Add retry context if this is a retry
        if build_attempt > 1 or execution_attempt > 1:
            retry_context = "\n\n## Previous Attempt Failed\n"
            if build_errors:
                retry_context += f"Build/Validation Errors:\n" + "\n".join(f"- {e}" for e in build_errors) + "\n"
            elif validation_errors:
                retry_context += f"Validation Errors:\n" + "\n".join(f"- {e}" for e in validation_errors) + "\n"
            if execution_errors:
                retry_context += f"Execution Errors:\n" + "\n".join(f"- {e}" for e in execution_errors) + "\n"
            retry_context += "Fix these issues in your query."
            system_prompt += retry_context
        
        # Add conversation context
        conversation_context_parts = []
        
        if prior_query_result:
            conversation_context_parts.append(f"## Similar Query Found in History\n")
            conversation_context_parts.append(f"Previous query (similarity: {prior_query_result['similarity_score']:.2f}):\n")
            conversation_context_parts.append(f"User message: {prior_query_result['message']}\n")
            conversation_context_parts.append(f"Query: {json.dumps(prior_query_result['query'], indent=2)}\n")
            conversation_context_parts.append("You can reuse and modify this query instead of building from scratch.")
        
        # Add context fields if user query references previous messages
        if context_fields:
            conversation_context_parts.append(f"\n## Fields from Previous Query\n")
            conversation_context_parts.append(f"**CRITICAL**: The user's current query references a previous query.")
            if context_measures:
                conversation_context_parts.append(f"**Measures from previous query**: {', '.join(context_measures)}")
                conversation_context_parts.append(f"**YOU MUST INCLUDE THESE MEASURES** in your current query!")
            if context_dimensions:
                conversation_context_parts.append(f"**Dimensions from previous query**: {', '.join(context_dimensions)}")
            conversation_context_parts.append(f"\n**Example**: If previous query used 'Sales' and user says 'break it down by region',")
            conversation_context_parts.append(f"you MUST include BOTH 'Sales' (from previous) AND 'Region' (new dimension) in query.fields!")
        
        if conversation_context_parts:
            system_prompt += "\n\n" + "\n".join(conversation_context_parts)
        
        # Build messages with conversation history context
        examples = prompt_registry.get_examples("agents/vizql/examples.yaml")
        messages = prompt_registry.build_few_shot_prompt(
            system_prompt,
            examples,
            f"Build query for: {user_query}"
        )
        
        # Add conversation history context before the current query
        # This helps the LLM understand references like "it", "that", "break it down"
        if message_history and len(message_history) > 0:
            # Extract relevant context from message history (all messages, no limit)
            conversation_context = []
            for i, msg in enumerate(message_history):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "user":
                    conversation_context.append(f"User: {content}")
                elif role == "assistant":
                    # Include assistant response and any query metadata
                    assistant_content = content
                    if msg.get("query_draft"):
                        assistant_content += f"\n[Previous query used: {json.dumps(msg['query_draft'], indent=2)}]"
                    if msg.get("query_results"):
                        results = msg["query_results"]
                        columns = results.get("columns", [])
                        row_count = results.get("row_count", 0)
                        assistant_content += f"\n[Previous query returned {row_count} rows with columns: {', '.join(columns)}]"
                    conversation_context.append(f"Assistant: {assistant_content}")
            
            if conversation_context:
                # Insert conversation history before the current user query
                history_text = "\n\n## Conversation History\n" + "\n\n".join(conversation_context)
                history_text += "\n\n**IMPORTANT**: Use the conversation history above to understand context. "
                history_text += "If the user says 'break it down by region' after asking about 'sales', "
                history_text += "they want to break down the SALES metric (from the previous query) by REGION."
                history_text += "\n\nIf previous queries used specific fields, reuse those fields in your query."
                
                # Add history context to the last user message
                if messages and messages[-1].get("role") == "user":
                    messages[-1]["content"] = history_text + "\n\n" + messages[-1]["content"]
                else:
                    # Add as separate message if structure is different
                    messages.insert(-1, {"role": "user", "content": history_text})
        
        # Schema should already be fetched above if needed
        
        # Track tool calls for this step
        tool_calls_made = []
        tool_result_summary_parts = []
        if enriched_schema:
            tool_calls_made.append("get_datasource_schema")
            # Build summary of schema
            fields = enriched_schema.get("fields", [])
            dimensions = [f for f in fields if f.get("fieldRole") == "DIMENSION"]
            measures = [f for f in fields if f.get("fieldRole") == "MEASURE"]
            if dimensions or measures:
                summary = f"Schema: {len(dimensions)} dimensions, {len(measures)} measures"
                tool_result_summary_parts.append(summary)
        if state.get("datasource_metadata"):
            tool_calls_made.append("get_datasource_metadata")
            metadata = state.get("datasource_metadata", {})
            ds_name = metadata.get("name", "datasource")
            tool_result_summary_parts.append(f"Metadata: {ds_name}")
        if state.get("query_reused"):
            tool_calls_made.append("get_prior_query")
            tool_result_summary_parts.append("Reused prior query")
        
        tool_result_summary = "; ".join(tool_result_summary_parts) if tool_result_summary_parts else None
        
        # Call LLM to build query
        ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL
        )
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        # Track token usage
        tokens_used = {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
            "total": response.tokens_used
        }
        
        # Debug: log response structure
        content_len = len(response.content) if response.content else 0
        logger.info(f"build_query response: content_len={content_len}, finish_reason={getattr(response, 'finish_reason', '')}, function_call={response.function_call is not None}")
        if content_len == 0 and response.raw_response:
            raw_keys = list(response.raw_response.keys()) if response.raw_response else []
            choice0 = response.raw_response.get("choices", [{}])[0] if response.raw_response.get("choices") else {}
            msg_keys = list(choice0.get("message", {}).keys()) if choice0.get("message") else []
            logger.warning(f"build_query empty content: raw_keys={raw_keys}, choice0.message keys={msg_keys}")
        elif content_len > 0:
            preview = repr(response.content[:300]) if response.content else ""
            logger.debug(f"build_query content preview: {preview}")
        
        # Parse query JSON
        try:
            content = (response.content or "").strip()
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
            
            # Try to extract JSON if there's extra content after it
            # Look for the first complete JSON object
            query_draft = None
            
            # First try: parse the entire content
            try:
                query_draft = json.loads(content)
            except json.JSONDecodeError:
                # Second try: find JSON object boundaries
                # Look for first { and matching }
                start_idx = content.find('{')
                if start_idx != -1:
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > start_idx:
                        json_str = content[start_idx:end_idx]
                        try:
                            query_draft = json.loads(json_str)
                            logger.info(f"Extracted JSON from response (char {start_idx} to {end_idx})")
                        except json.JSONDecodeError:
                            pass
            
            # Third try: look for JSON array if object didn't work
            if query_draft is None:
                start_idx = content.find('[')
                if start_idx != -1:
                    bracket_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '[':
                            bracket_count += 1
                        elif content[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > start_idx:
                        json_str = content[start_idx:end_idx]
                        try:
                            query_draft = json.loads(json_str)
                            logger.info(f"Extracted JSON array from response")
                        except json.JSONDecodeError:
                            pass
            
            if query_draft is None:
                # Log the problematic content for debugging
                content_preview = repr(content[:800]) if content else "(empty)"
                logger.error(f"Could not extract JSON from response. content_len={len(content)}, content_preview={content_preview}")
                if response.function_call:
                    logger.error(f"Response had function_call (unused): name={response.function_call.name}, args_len={len(response.function_call.arguments or '')}")
                raise json.JSONDecodeError("Could not extract valid JSON from response", content, 0)
            
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
            
            # CRITICAL: Ensure fields array exists and is populated
            if "fields" not in query_draft.get("query", {}):
                query_draft["query"]["fields"] = []
            
            # Validate that fields array is not empty
            fields = query_draft.get("query", {}).get("fields", [])
            if not fields or len(fields) == 0:
                error_msg = (
                    "Query must have at least one field in query.fields array. "
                    f"Schema available: {bool(schema or enriched_schema)}. "
                    f"User query: {user_query}"
                )
                logger.error(error_msg)
                logger.error(f"Query draft structure: {json.dumps(query_draft, indent=2)}")
                raise ValueError(error_msg)
            
            # Save copy before pre-validation rewrites (for detecting if query was modified)
            query_before_rewrites = copy.deepcopy(query_draft)
            
            # CRITICAL: Apply automatic date function detection and correction
            query_draft = detect_and_apply_date_functions(query_draft, user_query, enriched_schema)
            # CRITICAL: Apply automatic COUNTD detection for "how many" queries
            query_draft = detect_and_apply_count_functions(query_draft, user_query, enriched_schema)
            # CRITICAL: Apply automatic context filter detection
            query_draft = detect_and_apply_context_filters(query_draft, user_query)
            # CRITICAL: Validate and correct SET filter values against enriched schema sample_values
            query_draft = validate_and_correct_filter_values(query_draft, enriched_schema)
            # CRITICAL: Adjust calculated field names to avoid conflicts with existing fields
            query_draft = adjust_calculated_field_names(query_draft, enriched_schema, schema)
            # CRITICAL: Remove fieldCaption from filter fields that have calculations
            query_draft = remove_fieldcaption_from_calculated_filters(query_draft)
            
            # Track if pre-validation rewrites were applied (for reasoning step)
            query_was_rewritten = query_draft != query_before_rewrites
            pre_validation_changes = ["date functions", "count functions", "context filters", "filter values", "calculated field names"] if query_was_rewritten else []
            
            # Log fields being added for debugging (after auto-fix)
            fields = query_draft.get("query", {}).get("fields", [])  # Refresh after auto-fix
            field_names = [f.get("fieldCaption", "unknown") for f in fields]
            logger.info(f"Query includes {len(fields)} fields: {field_names}")
            
            # Check if fields match user query intent (including context fields from conversation)
            user_query_lower = user_query.lower()
            user_mentioned_fields = []
            for field_name in field_names:
                field_lower = field_name.lower()
                # Check if field name or parts of it are mentioned in user query OR in context
                if (field_lower in user_query_lower or 
                    any(word in user_query_lower for word in field_lower.split()) or
                    field_name in context_fields):
                    user_mentioned_fields.append(field_name)
            
            if len(user_mentioned_fields) < len(field_names):
                extra_fields = [f for f in field_names if f not in user_mentioned_fields]
                if context_fields:
                    logger.info(
                        f"Query includes fields from conversation context: {context_fields}. "
                        f"Extra fields: {extra_fields}"
                    )
                else:
                    logger.warning(
                        f"Query includes fields not explicitly mentioned in user query: {extra_fields}. "
                        f"User query: '{user_query}'. "
                        f"Only include fields the user explicitly requested!"
                    )
            
            query_version = state.get("query_version", 0)
            if query_version == 0:
                query_version = 1
            
            reasoning_steps.append({
                "node": "build_query",
                "timestamp": datetime.utcnow().isoformat(),
                "action": "query_built",
                "query_reused": prior_query_result is not None,
                "fields_count": len(query_draft.get("query", {}).get("fields", []))
            })
            
            result = {
                **state,
                "query_draft": query_draft,
                "query_version": query_version,
                "schema": schema,
                "enriched_schema": enriched_schema if enriched_schema else state.get("enriched_schema"),
                "query_reused": prior_query_result is not None,
                "query_was_rewritten": query_was_rewritten,
                "pre_validation_changes": pre_validation_changes,
                "reasoning": response.content,
                "reasoning_steps": reasoning_steps,
                "build_attempt": build_attempt,
                "execution_attempt": execution_attempt,
                "build_errors": None,
                "current_thought": f"Build attempt {build_attempt}: Built query version {query_version} with {len(query_draft.get('query', {}).get('fields', []))} fields",
                "step_metadata": {
                    "tool_calls": tool_calls_made,
                    "tokens": tokens_used,
                    "build_attempt": build_attempt,
                    "query_draft": query_draft,
                    "tool_result_summary": tool_result_summary
                }
            }
            
            # Clear error field if retrying after execution failure
            # This is critical so route_after_validation doesn't route to error_handler
            if should_clear_error:
                result["error"] = None
                result["execution_errors"] = None
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            # Handle JSON parsing errors and validation errors
            error_msg = str(e)
            response_preview = response.content[:1000] if response.content else "(empty)"
            logger.error(
                f"build_query parse/validation failed: {type(e).__name__}: {error_msg}. "
                f"content_len={len(response.content or '')}, preview={repr(response_preview[:200])}"
            )
            if response.raw_response and not response.content:
                logger.error(f"raw_response choices[0].message: {list(response.raw_response.get('choices', [{}])[0].get('message', {}).keys())}")
            
            # Check if it's a fields validation error
            if "fields" in error_msg.lower() or "field" in error_msg.lower() or isinstance(e, ValueError):
                error_msg = (
                    f"Query validation failed: {error_msg}. "
                    "The LLM did not include any fields in the query. "
                    "This may happen if the schema is missing or the user query is unclear."
                )
                logger.error(f"Query validation error: {error_msg}")
            else:
                # JSON parsing error
                logger.error(f"Failed to parse query JSON: {e}")
                logger.error(f"Response preview (first 1000 chars): {response_preview}")
                logger.error(f"Full response length: {len(response.content) if response.content else 0} chars")
                error_msg = f"Failed to parse query JSON: {error_msg}. The LLM response may contain extra text after the JSON. Check logs for full response."
            
            reasoning_steps.append({
                "node": "build_query",
                "timestamp": datetime.utcnow().isoformat(),
                "action": "error",
                "error": error_msg,
                "response_preview": response_preview if isinstance(e, json.JSONDecodeError) else None
            })
            return {
                **state,
                "error": error_msg,
                "query_draft": None,
                "build_attempt": build_attempt,
                "execution_attempt": execution_attempt,
                "reasoning_steps": reasoning_steps,
                "current_thought": f"Build attempt {build_attempt} failed: {error_msg[:150]}",
                "step_metadata": {
                    "tool_calls": tool_calls_made if 'tool_calls_made' in locals() else [],
                    "tokens": tokens_used if 'tokens_used' in locals() else None,
                    "build_attempt": build_attempt,
                    "query_draft": None,  # Explicitly set to None so frontend knows this build failed
                    "tool_result_summary": tool_result_summary if 'tool_result_summary' in locals() else None
                }
            }
        except Exception as e:
            logger.error(f"Error building query: {e}", exc_info=True)
            reasoning_steps.append({
                "node": "build_query",
                "timestamp": datetime.utcnow().isoformat(),
                "action": "error",
                "error": str(e)
            })
            return {
                **state,
                "error": f"Failed to build query: {str(e)}",
                "query_draft": None,
                "build_attempt": build_attempt,
                "execution_attempt": execution_attempt,
                "reasoning_steps": reasoning_steps,
                "current_thought": f"Build attempt {build_attempt} failed: {str(e)[:150]}",
                "step_metadata": {
                    "tool_calls": tool_calls_made if 'tool_calls_made' in locals() else [],
                    "tokens": tokens_used if 'tokens_used' in locals() else None,
                    "build_attempt": build_attempt,
                    "query_draft": None,
                    "tool_result_summary": tool_result_summary if 'tool_result_summary' in locals() else None
                }
            }
    except Exception as e:
        # Catch any exceptions that escape the inner try blocks
        logger.error(f"Unexpected error in build_query_node: {e}", exc_info=True)
        reasoning_steps = state.get("reasoning_steps", [])
        build_attempt = state.get("build_attempt", 1)
        execution_attempt = state.get("execution_attempt", 1)
        reasoning_steps.append({
            "node": "build_query",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "error",
            "error": f"Unexpected error: {str(e)}"
        })
        return {
            **state,
            "error": f"Failed to build query: {str(e)}",
            "query_draft": None,
            "build_attempt": build_attempt,
            "execution_attempt": execution_attempt,
            "reasoning_steps": reasoning_steps,
            "current_thought": f"Build attempt {build_attempt} failed: {str(e)[:150]}",
            "step_metadata": {
                "build_attempt": build_attempt,
                "query_draft": None,
                "tool_result_summary": None
            }
        }
