"""Get data node using tool calls."""
import json
import logging
from typing import Dict, Any

from app.services.agents.vizql_tool_use.state import VizQLToolUseState
from app.services.agents.vizql_tool_use.tools import VizQLTools
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_data_node(state: VizQLToolUseState) -> Dict[str, Any]:
    import time as time_module
    node_start_time = time_module.time()
    logger.info(f"=== GET_DATA NODE STARTED at {node_start_time} ===")
    """
    Step 1: Use tools to get data needed to answer user query.
    
    This node:
    1. Calls LLM with tool definitions
    2. LLM decides which tools to use
    3. Executes tools and collects results
    4. Returns raw data for summarization
    """
    try:
        user_query = state.get("user_query", "")
        message_history = state.get("message_history", [])
        site_id = state.get("site_id")
        datasource_id = state.get("datasource_id")
        
        logger.info(f"Get data node: user_query='{user_query}'")
        logger.info(f"Site ID: {site_id}, Datasource ID: {datasource_id}")
        
        # Initialize Tableau client with site_id if available
        from app.services.tableau.client import TableauClient
        if site_id:
            tableau_client = TableauClient(site_id=site_id)
            logger.info(f"Initialized TableauClient with site_id: {site_id}")
        else:
            tableau_client = TableauClient()
            logger.warning("No site_id provided, using default from settings")
        
        # Ensure Tableau client is authenticated before using tools
        try:
            await tableau_client._ensure_authenticated()
            logger.info("Tableau client authenticated successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate Tableau client: {e}", exc_info=True)
            return {
                **state,
                "error": f"Tableau authentication failed: {str(e)}",
                "raw_data": None
            }
        
        # Get API key and model from state for tools (needed for LLM calls in build_query)
        api_key = state.get("api_key")
        model = state.get("model")
        logger.info(f"Initializing tools with api_key={'present' if api_key else 'None'}, model={model}")
        
        # Initialize tools
        tools = VizQLTools(
            site_id=site_id,
            datasource_id=datasource_id,
            tableau_client=tableau_client,
            message_history=message_history,
            api_key=api_key,
            model=model
        )
        
        # Get prompt
        system_prompt = prompt_registry.get_prompt("agents/vizql_tool_use/get_data.txt")
        
        # Build messages with full conversation history
        # CRITICAL: Pass actual user/assistant messages, not a summary
        # This allows the LLM to naturally reference previous context
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add message history as actual conversation messages (not summary)
        if message_history:
            # This preserves full context including data structure and natural language responses
            for msg in message_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                if role in ["user", "assistant"] and content:
                    msg_content = content
                    
                    # For assistant messages with data, append structured dimension values
                    # This provides clear context for follow-up queries
                    if role == "assistant" and "data_metadata" in msg and msg["data_metadata"]:
                        metadata = msg["data_metadata"]
                        dimension_values = metadata.get("dimension_values", {})
                        
                        if dimension_values:
                            # Format dimension values for easy LLM reference
                            from app.services.agents.vizql_tool_use.context_extractor import format_context_for_llm
                            context_str = format_context_for_llm(dimension_values)
                            msg_content = content + context_str
                            logger.info(f"Added {len(dimension_values)} dimension contexts to message")
                    
                    messages.append({"role": role, "content": msg_content})
            
            logger.info(f"Added {len([m for m in messages if m.get('role') in ['user', 'assistant']])} conversation messages to context")
        
        # Add current user query
        messages.append({"role": "user", "content": user_query})
        
        # Add explicit instruction to use tools and structured context
        messages.append({
            "role": "system",
            "content": """CRITICAL INSTRUCTIONS:

1. You must execute tools to get data. Do not explain - call build_query and query_datasource to get actual results.

2. For 'top N by X' queries, use topN parameter in build_query.

3. Use structured context from previous messages:
   - Previous assistant messages include "[Context from previous query]" sections
   - These show exactly which dimension values were returned (cities, products, etc.)
   - When user says "those", "each of those", etc., use values from the context section
   - Do NOT use all values from the dataset - only use what's in the structured context

Example:
Previous message shows:
  [Context from previous query]
    - City: Houston, Philadelphia, Seattle
User query: "show me sales for those cities"
Your action: Use filter with ["Houston", "Philadelphia", "Seattle"]"""
        })
        
        # Get API key and model from state or use defaults
        api_key = state.get("api_key")
        model = state.get("model")
        logger.info(f"get_data_node: model from state = {model}")
        
        if not model:
            logger.warning("No model in state, attempting to get default model")
            # Try to get default model dynamically
            try:
                from app.services.gateway.model_utils import get_default_model
                # Get provider from model if available, or use OpenAI as default
                model = await get_default_model(provider="openai", authorization=api_key)
                logger.info(f"Got default model: {model}")
            except Exception as e:
                logger.warning(f"Failed to get default model dynamically: {e}, using gpt-4")
                model = "gpt-4"  # Last resort fallback
        
        # If no API key in state, try to get from settings
        if not api_key:
            try:
                # Try OpenAI first, then Anthropic
                api_key = settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY
            except AttributeError:
                pass
        
        # Validate API key is present
        if not api_key or not api_key.strip():
            error_msg = (
                "API key is required for LLM calls. "
                "Please provide an API key via Authorization header or configure OPENAI_API_KEY/ANTHROPIC_API_KEY in settings."
            )
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "raw_data": None
            }
        
        logger.info(f"Using model: {model}, API key: {'present' if api_key else 'missing'}")
        
        # Call LLM with tools
        # Use longer timeout (5 minutes) for processing large data to avoid timeouts
        ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key,
            timeout=300  # 5 minutes for large data processing
        )
        tool_calls_made = []
        raw_data = None
        max_iterations = 3  # Prevent infinite loops
        iteration = 0
        current_thought = f"Analyzing query: {user_query}"
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"=== GET_DATA ITERATION {iteration}/{max_iterations} ===")
            logger.info(f"Tool calls made so far: {len(tool_calls_made)}")
            logger.info(f"Tool call sequence: {[tc.get('tool') for tc in tool_calls_made]}")
            logger.info(f"Raw data present: {raw_data is not None}")
            logger.info(f"Current messages count: {len(messages)}")
            
            # Get function definitions (already in OpenAI format)
            functions = tools.get_tool_definitions()
            logger.info(f"Available functions: {[f.get('name') for f in functions]}")
            logger.info(f"Calling LLM with model={model}, functions_count={len(functions) if functions else 0}")
            
            # Check if model requires new tools format (instead of old functions format)
            # Newer models (gpt-4o, gpt-4-turbo, gpt-5, etc.) use tools format
            use_tools_format = model and any(x in model.lower() for x in ["gpt-4o", "gpt-4-turbo", "gpt-5", "o1", "o3"])
            
            # Track reasoning: what the LLM is thinking
            if tool_calls_made:
                last_tool = tool_calls_made[-1]
                current_thought = f"Processing result from {last_tool['tool']}..."
            else:
                current_thought = f"Analyzing query: {user_query}"
            
            try:
                # For first iteration, if we have functions, require function calling
                # This ensures the LLM actually executes tools instead of explaining
                function_call_mode = "auto" if functions else None
                if iteration == 1 and functions and not tool_calls_made:
                    # First call with functions available - strongly encourage function calling
                    function_call_mode = "auto"
                
                # For newer models, use tools format; for older models, use functions format
                if use_tools_format and functions:
                    # Convert functions to tools format: wrap each function in {"type": "function", "function": {...}}
                    tools_format = [{"type": "function", "function": f} for f in functions]
                    tool_choice = "auto" if function_call_mode == "auto" else None
                    response = await ai_client.chat(
                        model=model,
                        messages=messages,
                        tools=tools_format,
                        tool_choice=tool_choice
                    )
                else:
                    # Use old functions format
                    response = await ai_client.chat(
                        model=model,
                        messages=messages,
                        functions=functions if functions else None,
                        function_call=function_call_mode
                    )
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error calling LLM: {error_msg}", exc_info=True)
                # If it's an authentication error, provide helpful message
                if "Authorization" in error_msg or "authentication" in error_msg.lower():
                    raise Exception(f"AI Gateway authentication failed. Please check your API key configuration. Error: {error_msg}")
                raise
            
            logger.info(f"LLM response - has function_call: {response.function_call is not None}, content: {response.content[:100] if response.content else 'None'}")
            
            # Update reasoning based on LLM response
            if response.content:
                current_thought = response.content[:200]  # Use LLM's reasoning as thought
            elif response.function_call:
                current_thought = f"Calling {response.function_call.name}..."
            
            # Check if LLM wants to call functions
            if response.function_call:
                # Execute function call
                tool_name = response.function_call.name
                try:
                    arguments = json.loads(response.function_call.arguments) if isinstance(response.function_call.arguments, str) else response.function_call.arguments
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse function arguments: {e}. Raw: {response.function_call.arguments}")
                    arguments = {}
                
                logger.info(f"=== TOOL CALL DETECTED ===")
                logger.info(f"Tool name: {tool_name}")
                logger.info(f"Tool arguments: {json.dumps(arguments, indent=2)}")
                logger.info(f"Arguments type: {type(arguments)}")
                logger.info(f"Previous tool calls made: {len(tool_calls_made)}")
                logger.info(f"Current iteration: {iteration}")
                logger.info(f"Using tools format: {use_tools_format}")
                
                # Validate required arguments and auto-fill from previous tool calls if needed
                if tool_name == "query_datasource" and "query" not in arguments:
                    # Try to get query from LATEST build_query tool call (iterate in reverse)
                    logger.warning("query_datasource called without query argument, checking previous tool calls")
                    for prev_tool_call in reversed(tool_calls_made):
                        if prev_tool_call.get("tool") == "build_query":
                            prev_result = prev_tool_call.get("result", {})
                            if isinstance(prev_result, dict) and prev_result.get("query"):
                                arguments["query"] = prev_result["query"]
                                logger.info(f"Auto-filled query from LATEST build_query tool call (iteration {tool_calls_made.index(prev_tool_call) + 1})")
                                break
                    
                    # If still no query, this is an error - add to conversation and continue
                    if "query" not in arguments:
                        error_msg = "query_datasource requires a 'query' argument. You must call build_query first to create a query."
                        logger.error(error_msg)
                        tool_result = {"error": error_msg}
                        # Add error message to conversation so LLM can retry
                        if use_tools_format:
                            tool_call_id = f"call_{tool_name}_{iteration}_error"
                            messages.append({
                                "role": "assistant",
                                "content": response.content or "",
                                "tool_calls": [{
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(arguments)
                                    }
                                }]
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(tool_result)
                            })
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": response.content or "",
                                "function_call": json.dumps({
                                    "name": tool_name,
                                    "arguments": json.dumps(arguments)
                                })
                            })
                            messages.append({
                                "role": "function",
                                "name": tool_name,
                                "content": json.dumps(tool_result)
                            })
                        # Continue loop to let LLM retry
                        continue
                
                # Update reasoning for tool execution
                current_thought = f"Executing {tool_name}..."
                
                try:
                    # Execute tool
                    logger.info(f"--- Executing tool: {tool_name} ---")
                    logger.info(f"Tool arguments being passed: {json.dumps(arguments, indent=2)}")
                    tool_result = await tools.execute_tool(tool_name, arguments)
                    logger.info(f"--- Tool execution completed: {tool_name} ---")
                    logger.info(f"Tool result type: {type(tool_result)}")
                    if isinstance(tool_result, dict):
                        logger.info(f"Tool result keys: {list(tool_result.keys())}")
                        # Log important fields
                        if "query" in tool_result:
                            logger.info(f"Tool result contains 'query' field: {str(tool_result.get('query'))[:200]}")
                        if "row_count" in tool_result:
                            logger.info(f"Tool result row_count: {tool_result.get('row_count')}")
                        if "error" in tool_result:
                            logger.warning(f"Tool result contains error: {tool_result.get('error')}")
                    else:
                        logger.info(f"Tool result (first 500 chars): {str(tool_result)[:500]}")
                    
                    # Update reasoning based on tool result
                    if tool_name == "build_query" and tool_result.get("query"):
                        current_thought = f"Built VizQL query successfully"
                    elif tool_name == "query_datasource" and tool_result.get("row_count", 0) > 0:
                        current_thought = f"Retrieved {tool_result.get('row_count')} rows from datasource"
                    elif tool_name == "get_datasource_metadata":
                        current_thought = f"Retrieved datasource metadata"
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error executing tool {tool_name}: {error_msg}", exc_info=True)
                    tool_result = {"error": error_msg}
                    current_thought = f"Error executing {tool_name}: {error_msg[:100]}"
                    
                    # If it's a missing argument error, add to conversation so LLM can retry
                    if "missing" in error_msg.lower() or "required" in error_msg.lower():
                        logger.warning(f"Missing argument error for {tool_name}, adding to conversation for retry")
                        if use_tools_format:
                            tool_call_id = f"call_{tool_name}_{iteration}_error"
                            messages.append({
                                "role": "assistant",
                                "content": response.content or "",
                                "tool_calls": [{
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(arguments)
                                    }
                                }]
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(tool_result)
                            })
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": response.content or "",
                                "function_call": json.dumps({
                                    "name": tool_name,
                                    "arguments": json.dumps(arguments)
                                })
                            })
                            messages.append({
                                "role": "function",
                                "name": tool_name,
                                "content": json.dumps(tool_result)
                            })
                        # Continue loop to let LLM retry with correct arguments
                        continue
                
                # Track tool call
                logger.info(f"--- Tracking tool call: {tool_name} ---")
                logger.info(f"Arguments: {json.dumps(arguments, indent=2)}")
                logger.info(f"Result type: {type(tool_result)}")
                if isinstance(tool_result, dict):
                    logger.info(f"Result keys: {list(tool_result.keys())}")
                    if "query" in tool_result:
                        logger.info(f"Result contains 'query': {str(tool_result.get('query'))[:200]}")
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": tool_result
                })
                logger.info(f"Total tool calls tracked: {len(tool_calls_made)}")
                logger.info(f"Tool call sequence: {[tc.get('tool') for tc in tool_calls_made]}")
                
                # Add assistant message and function result to conversation
                # Handle both old (functions) and new (tools) formats
                logger.info(f"--- Adding tool call to conversation history ---")
                logger.info(f"Using tools format: {use_tools_format}")
                logger.info(f"Tool: {tool_name}")
                logger.info(f"Current messages count: {len(messages)}")
                if use_tools_format:
                    # New format: use tool_calls and tool_call_id
                    # Extract tool_call_id from response if available
                    tool_call_id = None
                    if hasattr(response, 'raw_response') and response.raw_response:
                        message = response.raw_response.get("choices", [{}])[0].get("message", {})
                        tool_calls = message.get("tool_calls", [])
                        if tool_calls:
                            tool_call_id = tool_calls[0].get("id")
                    
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [{
                            "id": tool_call_id or f"call_{tool_name}_{iteration}",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": response.function_call.arguments if isinstance(response.function_call.arguments, str) else json.dumps(response.function_call.arguments)
                            }
                        }]
                    })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id or f"call_{tool_name}_{iteration}",
                        "content": json.dumps(tool_result)
                    })
                    logger.info(f"Added assistant message with tool_calls and tool response message")
                    logger.info(f"Tool call ID: {tool_call_id or f'call_{tool_name}_{iteration}'}")
                    logger.info(f"Tool result content length: {len(json.dumps(tool_result))}")
                else:
                    # Old format: use function_call
                    function_call_str = json.dumps({
                        "name": tool_name,
                        "arguments": response.function_call.arguments if isinstance(response.function_call.arguments, str) else json.dumps(response.function_call.arguments)
                    })
                    
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "function_call": function_call_str
                    })
                    
                    messages.append({
                        "role": "function",
                        "name": tool_name,
                        "content": json.dumps(tool_result)
                    })
                    logger.info(f"Added assistant message with function_call and function response message")
                    logger.info(f"Function result content length: {len(json.dumps(tool_result))}")
                
                logger.info(f"Messages count after adding tool call: {len(messages)}")
                # If this was query_datasource or get_datasource_metadata, we likely have our data
                if tool_name in ["query_datasource", "get_datasource_metadata", "get_previous_results"]:
                    raw_data = tool_result
                    logger.info(f"Set raw_data from tool {tool_name}")
                    
                    # If we successfully retrieved data from query_datasource, consider stopping
                    # Prevent infinite loops: if we've executed query_datasource multiple times with data, stop
                    if tool_name == "query_datasource" and isinstance(tool_result, dict):
                        row_count = tool_result.get("row_count", 0)
                        query_exec_count = sum(1 for tc in tool_calls_made if tc.get("tool") == "query_datasource")
                        if row_count > 0 and query_exec_count >= 2:
                            # We have data and have executed query multiple times - stop to prevent loop
                            logger.info(f"Retrieved {row_count} rows from query_datasource (execution #{query_exec_count}). Stopping to prevent infinite loop.")
                            break
            else:
                # No more function calls, LLM is done
                final_content = response.content or ""
                logger.info(f"LLM finished without function calls. Content: {final_content[:200]}")
                
                # Check if LLM output JSON tool calls in content instead of using function calling
                # This can happen if the model doesn't properly support function calling
                if final_content and not tool_calls_made:
                    # Try to parse JSON tool calls from content
                    parsed_tools = []
                    logger.info(f"Attempting to parse JSON tool calls from content (length: {len(final_content)})")
                    
                    # Extract complete JSON objects from content (handles multi-line JSON)
                    content_cleaned = final_content.strip()
                    
                    # Try to find and parse each JSON object by finding balanced braces
                    i = 0
                    while i < len(content_cleaned):
                        # Find next opening brace
                        if content_cleaned[i] == '{':
                            # Find matching closing brace
                            brace_count = 0
                            json_start = i
                            json_end = -1
                            
                            for j in range(i, len(content_cleaned)):
                                if content_cleaned[j] == '{':
                                    brace_count += 1
                                elif content_cleaned[j] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        json_end = j + 1
                                        break
                            
                            if json_end > 0:
                                json_str = content_cleaned[json_start:json_end]
                                try:
                                    tool_data = json.loads(json_str)
                                    if isinstance(tool_data, dict) and "tool" in tool_data:
                                        tool_name = tool_data.get("tool")
                                        args = tool_data.get("args", {})
                                        parsed_tools.append((tool_name, args))
                                        logger.info(f"Parsed tool call from content: {tool_name} with args: {args}")
                                        i = json_end  # Move past this JSON object
                                        continue
                                except json.JSONDecodeError as e:
                                    logger.debug(f"Failed to parse JSON: {json_str[:100]}, error: {e}")
                        i += 1
                    
                    # Fallback: try parsing each line separately
                    if not parsed_tools:
                        lines = content_cleaned.split('\n')
                        logger.info(f"Trying line-by-line parsing, {len(lines)} lines")
                        for line in lines:
                            line = line.strip()
                            if not line or not line.startswith('{'):
                                continue
                            try:
                                tool_data = json.loads(line)
                                if isinstance(tool_data, dict) and "tool" in tool_data:
                                    tool_name = tool_data.get("tool")
                                    args = tool_data.get("args", {})
                                    parsed_tools.append((tool_name, args))
                                    logger.info(f"Parsed tool call from line: {tool_name} with args: {args}")
                            except json.JSONDecodeError:
                                continue
                    
                    # Execute parsed tool calls
                    if parsed_tools:
                        logger.warning(f"=== PARSED TOOL CALLS FROM CONTENT ===")
                        logger.warning(f"Found {len(parsed_tools)} tool calls as JSON strings instead of function calls")
                        for idx, (tool_name, args) in enumerate(parsed_tools):
                            logger.info(f"--- Parsed tool call #{idx + 1}/{len(parsed_tools)} ---")
                            logger.info(f"Tool name: {tool_name}")
                            logger.info(f"Tool args: {json.dumps(args, indent=2)}")
                            logger.info(f"Args type: {type(args)}")
                            try:
                                logger.info(f"Executing parsed tool: {tool_name}")
                                tool_result = await tools.execute_tool(tool_name, args)
                                tool_calls_made.append({
                                    "tool": tool_name,
                                    "arguments": args,
                                    "result": tool_result
                                })
                                logger.info(f"✓ Successfully executed parsed tool: {tool_name}")
                                logger.info(f"Tool result type: {type(tool_result)}")
                                if isinstance(tool_result, dict):
                                    logger.info(f"Tool result keys: {list(tool_result.keys())}")
                                    if "query" in tool_result:
                                        logger.info(f"Tool result contains 'query': {str(tool_result.get('query'))[:200]}")
                                logger.info(f"Total tool calls made so far: {len(tool_calls_made)}")
                                
                                # Update raw_data if this tool returns data
                                if tool_name in ["query_datasource", "get_datasource_metadata", "get_previous_results"]:
                                    raw_data = tool_result
                                
                                # Add to conversation history for next iteration
                                # Truncate large data results to avoid timeout (keep full data in raw_data)
                                tool_result_for_history = tool_result
                                if isinstance(tool_result, dict) and "data" in tool_result:
                                    data_rows = tool_result.get("data", [])
                                    if len(data_rows) > 50:  # Truncate if more than 50 rows
                                        truncated_result = tool_result.copy()
                                        truncated_result["data"] = data_rows[:50]
                                        truncated_result["row_count"] = len(data_rows)
                                        truncated_result["_truncated"] = True
                                        truncated_result["_total_rows"] = len(data_rows)
                                        tool_result_for_history = truncated_result
                                        logger.info(f"Truncated tool result from {len(data_rows)} to 50 rows for conversation history")
                                
                                if use_tools_format:
                                    tool_call_id = f"call_{tool_name}_{iteration}_{len(tool_calls_made)}"
                                    messages.append({
                                        "role": "assistant",
                                        "content": "",  # Use empty string instead of None
                                        "tool_calls": [{
                                            "id": tool_call_id,
                                            "type": "function",
                                            "function": {
                                                "name": tool_name,
                                                "arguments": json.dumps(args)
                                            }
                                        }]
                                    })
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "content": json.dumps(tool_result_for_history)
                                    })
                                else:
                                    messages.append({
                                        "role": "assistant",
                                        "content": "",  # Use empty string instead of None
                                        "function_call": json.dumps({
                                            "name": tool_name,
                                            "arguments": json.dumps(args)
                                        })
                                    })
                                    messages.append({
                                        "role": "function",
                                        "name": tool_name,
                                        "content": json.dumps(tool_result_for_history)
                                    })
                            except Exception as e:
                                logger.error(f"Error executing parsed tool {tool_name}: {e}", exc_info=True)
                                # Continue with next tool even if this one fails
                                continue
                        # Continue loop to let LLM process tool results
                        continue
                
                # Check if we have successfully retrieved data and should stop
                has_successful_query = any(
                    tc.get("tool") == "query_datasource" and 
                    isinstance(tc.get("result"), dict) and 
                    tc.get("result", {}).get("row_count", 0) > 0
                    for tc in tool_calls_made
                )
                
                # Prevent infinite loops: if we've executed the same query multiple times, stop
                query_execution_count = sum(1 for tc in tool_calls_made if tc.get("tool") == "query_datasource")
                if query_execution_count >= 3:
                    logger.warning(f"Executed query_datasource {query_execution_count} times. Stopping to prevent infinite loop.")
                    if raw_data:
                        logger.info("Using existing raw_data. Stopping iteration.")
                        break
                
                # If we have data and LLM is done (no more function/tool calls), stop
                if has_successful_query and raw_data and not response.function_call:
                    logger.info("Successfully retrieved data and LLM finished. Stopping iteration.")
                    break
                
                # Check if LLM is explaining instead of executing
                # If we have metadata but no query results, and LLM is explaining, prompt it to execute
                has_metadata = any(tc.get("tool") == "get_datasource_metadata" for tc in tool_calls_made)
                has_query_results = any(tc.get("tool") in ["build_query", "query_datasource"] for tc in tool_calls_made)
                
                if has_metadata and not has_query_results and final_content:
                    # LLM got metadata but is explaining instead of executing query
                    # Check if the query requires aggregation/filtering/topN
                    query_requires_execution = any(keyword in user_query.lower() for keyword in [
                        "top", "bottom", "by", "total", "sum", "average", "count", "group", "filter", "where"
                    ])
                    
                    if query_requires_execution and iteration < max_iterations - 1:
                        logger.warning("LLM explained instead of executing query. Prompting to execute tools.")
                        # Add a user message prompting execution (more direct than system)
                        messages.append({
                            "role": "user",
                            "content": f"Please execute the tools to get the data. For '{user_query}', you need to call build_query and query_datasource. Do not explain - execute the tools now."
                        })
                        # Continue the loop instead of breaking
                        continue
                
                # If we have content but no data yet, use content as data
                if not raw_data and final_content:
                    raw_data = {"content": final_content}
                    logger.info("Using LLM content as raw_data")
                
                # Stop if LLM finished without function/tool calls and we have data
                if raw_data and final_content and not response.function_call:
                    logger.info("LLM finished without function calls and we have data. Stopping.")
                    break
                
                # Stop if LLM finished without function/tool calls (even without data, let summarize handle it)
                if final_content and not response.function_call:
                    logger.info("LLM finished without function calls. Stopping.")
                    break
        
        # If we don't have raw_data yet, use the last tool result
        if raw_data is None and tool_calls_made:
            raw_data = tool_calls_made[-1]["result"]
            logger.info(f"Using last tool result as raw_data: {tool_calls_made[-1]['tool']}")
        
        logger.info(f"Get data node complete: {len(tool_calls_made)} tool calls made, raw_data is {'present' if raw_data else 'None'}")
        
        # Extract VizQL query from tool calls if available
        logger.info(f"=== EXTRACTING VIZQL QUERY ===")
        logger.info(f"Total tool calls to check: {len(tool_calls_made)}")
        vizql_query = None
        for idx, tool_call in enumerate(tool_calls_made):
            tool_name = tool_call.get("tool", "unknown")
            logger.info(f"Checking tool call #{idx + 1}: {tool_name}")
            if tool_name in ["build_query", "query_datasource"]:
                result = tool_call.get("result", {})
                logger.info(f"Tool {tool_name} result type: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"Tool {tool_name} result keys: {list(result.keys())}")
                    vizql_query = result.get("query") or result.get("query_draft")
                    if vizql_query:
                        logger.info(f"✓ Found VizQL query in tool_call from {tool_name}")
                        logger.info(f"Query type: {type(vizql_query)}")
                        logger.info(f"Query preview: {str(vizql_query)[:300]}")
                        break
                    else:
                        logger.info(f"No 'query' or 'query_draft' in {tool_name} result")
                else:
                    logger.info(f"Tool {tool_name} result is not a dict: {type(result)}")
        
        if not vizql_query:
            logger.warning("No VizQL query found in any tool calls")
        
        # Fallback: If no tool calls were made and no data retrieved, try to infer what tool to use
        if raw_data is None and not tool_calls_made:
            logger.warning("No tool calls made by LLM. Attempting fallback based on query analysis.")
            
            # Simple heuristic: if query looks like "how many X", try get_datasource_metadata
            query_lower = user_query.lower()
            if any(pattern in query_lower for pattern in ["how many", "what's the min", "what's the max", "what fields", "list all"]):
                logger.info("Query matches metadata pattern, calling get_datasource_metadata as fallback")
                try:
                    raw_data = await tools.get_datasource_metadata(include_statistics=True)
                    tool_calls_made.append({
                        "tool": "get_datasource_metadata",
                        "arguments": {"include_statistics": True},
                        "result": raw_data
                    })
                    logger.info("Fallback get_datasource_metadata succeeded")
                except Exception as e:
                    logger.error(f"Fallback get_datasource_metadata failed: {e}", exc_info=True)
        
        if raw_data is None:
            logger.error("No raw_data retrieved after all iterations. Tool calls made: " + str([tc['tool'] for tc in tool_calls_made]))
            logger.error(f"User query: {user_query}")
            logger.error(f"Available functions: {[f.get('name') for f in tools.get_tool_definitions()]}")
        
        # Build return state with all updates
        updated_state = {
            **state,
            "raw_data": raw_data,
            "tool_calls": tool_calls_made,
            "query_draft": vizql_query  # Store query for extraction by chat.py
        }
        
        # Add current_thought if we have one
        if 'current_thought' in locals() and current_thought:
            updated_state["current_thought"] = current_thought
            logger.info(f"Returning state with current_thought: {current_thought[:100]}")
        
        logger.info(f"=== GET_DATA NODE COMPLETE ===")
        logger.info(f"Tool calls made: {len(tool_calls_made)}")
        logger.info(f"Tool call names: {[tc.get('tool') for tc in tool_calls_made]}")
        logger.info(f"Query draft present: {vizql_query is not None}")
        logger.info(f"Raw data present: {raw_data is not None}")
        if vizql_query:
            logger.info(f"Query draft preview: {str(vizql_query)[:300]}")
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Error in get_data_node: {e}", exc_info=True)
        return {
            **state,
            "error": str(e)
        }


def _format_message_history(message_history: list) -> str:
    """Format message history for context."""
    formatted = []
    for msg in message_history[-5:]:  # Last 5 messages
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            # Show more content (up to 500 chars) to capture lists, tables, etc.
            formatted.append(f"{role}: {content[:500]}")
        # Also include data if available (for assistant messages)
        if role == "assistant" and "data" in msg and msg["data"]:
            data = msg["data"]
            if isinstance(data, dict):
                columns = data.get("columns", [])
                data_rows = data.get("data", [])
                if columns and data_rows:
                    # Show column names and first few rows
                    formatted.append(f"  Data columns: {', '.join(str(c) for c in columns[:10])}")
                    if len(data_rows) > 0:
                        formatted.append(f"  Data rows: {len(data_rows)} rows")
                        # Show first row as example
                        if len(data_rows) > 0:
                            first_row = data_rows[0]
                            formatted.append(f"  First row example: {str(first_row)[:200]}")
    return "\n".join(formatted)
