"""Get data node using tool calls for Summary agent."""
import json
import logging
from typing import Dict, Any

from langchain_core.runnables.config import ensure_config

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.tools import SummaryTools, _extract_embedded_to_views_data, _sanitize_view_id
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


async def get_data_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Tool-use node: LLM calls get_embed_data (on canvas), or query_view_metadata + get_rest_summary_data/get_exported_image (not on canvas).
    Returns views_data, views_metadata, view_images.
    """
    try:
        view_ids = state.get("context_views", [])
        embedded_state = state.get("embedded_state") or {}
        user_query = state.get("user_query", "")
        message_history = state.get("messages", []) or []

        if not view_ids:
            return {
                **state,
                "error": "No view in context. Please add a view first.",
                "views_data": {},
                "views_metadata": {},
                "view_images": {},
            }

        # Include embedded_state keys for tool validation
        all_view_ids = list(set(view_ids + [_sanitize_view_id(k) for k in embedded_state]))

        config = ensure_config()
        tableau_client = config.get("configurable", {}).get("tableau_client")
        if not tableau_client and view_ids:
            try:
                tableau_client = TableauClient()
                await tableau_client._ensure_authenticated()
            except Exception as e:
                logger.warning(f"TableauClient init failed: {e}")

        tools = SummaryTools(
            embedded_state=embedded_state,
            view_ids=all_view_ids,
            tableau_client=tableau_client,
        )

        # Pre-populate from embedded_state for views with successful capture (avoids LLM incorrectly using get_exported_image)
        # Use per-sheet format for dashboards (view_id_sheet_0, view_id_sheet_1, ...) so summarizer gets all metrics
        views_data: Dict[str, Any] = {}
        views_metadata: Dict[str, Any] = {}
        view_images: Dict[str, str] = {}

        def _has_data_for_view(vid: str) -> bool:
            c = _sanitize_view_id(vid)
            if c in views_data or c in view_images:
                return True
            prefix = f"{c}_sheet_"
            return any(k.startswith(prefix) for k in views_data if isinstance(k, str))

        for vid in view_ids:
            emb = embedded_state.get(vid) or embedded_state.get(_sanitize_view_id(vid))
            if emb and not emb.get("capture_error") and (emb.get("summary_data") or emb.get("sheets_data")):
                vd, vm = _extract_embedded_to_views_data(vid, emb)
                views_data.update(vd)
                views_metadata.update(vm)
                logger.info(f"Pre-populated views_data from embedded_state for view {vid} ({len(vd)} sheet(s))")

        views_needing_data = [v for v in view_ids if not _has_data_for_view(v)]
        if not views_needing_data:
            thought = f"Retrieved data for {len(views_data)} view(s) from embedded state."
            return {**state, "views_data": views_data, "views_metadata": views_metadata, "view_images": view_images, "current_thought": thought}

        system_prompt = prompt_registry.get_prompt("agents/summary/get_data.txt")
        messages = [{"role": "system", "content": system_prompt}]

        for msg in message_history[-10:]:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        embedded_keys_success = [k for k, v in (embedded_state or {}).items() if not v.get("capture_error") and (v.get("summary_data") or v.get("sheets_data"))]
        ctx = f"Views in context: {view_ids}. Views ALREADY have embedded data (skip these): {embedded_keys_success}. Views needing data via REST: {views_needing_data}. User query: {user_query}"
        messages.append({"role": "user", "content": ctx})

        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        use_tools_format = model and any(x in model.lower() for x in ["gpt-4o", "gpt-4-turbo", "gpt-5", "o1", "o3", "claude"])
        tool_defs = tools.get_tool_definitions()
        tools_payload = [{"type": "function", "function": f} for f in tool_defs] if use_tools_format else tool_defs

        ai_client = UnifiedAIClient(gateway_url=settings.BACKEND_API_URL, timeout=120)
        tool_calls_made = []
        iteration = 0

        while iteration < MAX_ITERATIONS:
            iteration += 1
            try:
                if use_tools_format:
                    response = await ai_client.chat(
                        model=model,
                        provider=provider,
                        messages=messages,
                        tools=tools_payload,
                        tool_choice="auto",
                    )
                else:
                    response = await ai_client.chat(
                        model=model,
                        provider=provider,
                        messages=messages,
                        functions=tool_defs,
                        function_call="auto",
                    )
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                return {**state, "error": str(e), "views_data": views_data, "views_metadata": views_metadata, "view_images": view_images}

            if not response.function_call:
                break

            tool_name = response.function_call.name
            try:
                args = json.loads(response.function_call.arguments) if isinstance(response.function_call.arguments, str) else response.function_call.arguments
            except json.JSONDecodeError:
                args = {}
            view_id = _sanitize_view_id(args.get("view_id", ""))

            try:
                result = await tools.execute_tool(tool_name, args)
            except Exception as e:
                result = {"error": str(e)}

            tool_calls_made.append({"tool": tool_name, "arguments": args, "result": result})

            if tool_name in ("get_embed_data", "get_rest_summary_data") and "error" not in result:
                if "sheets" in result:
                    for k, d in result["sheets"].items():
                        views_data[k] = {"columns": d.get("columns", []), "data": d.get("data", []), "row_count": d.get("row_count", 0)}
                        views_metadata[k] = {"id": k, "name": d.get("name", k)}
                else:
                    views_data[view_id] = {"columns": result.get("columns", []), "data": result.get("data", []), "row_count": result.get("row_count", 0)}
                    views_metadata[view_id] = {"id": view_id, "name": result.get("name", view_id)}
            elif tool_name == "get_exported_image" and "error" not in result:
                b64 = result.get("image_base64")
                if b64:
                    view_images[view_id] = b64
                    views_metadata[view_id] = views_metadata.get(view_id) or {"id": view_id, "name": view_id}

            raw = getattr(response, "raw_response", None) or {}
            tc = raw.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
            tool_call_id = tc[0].get("id") if tc else None

            if use_tools_format:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [{
                        "id": tool_call_id or f"call_{tool_name}_{iteration}",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": response.function_call.arguments if isinstance(response.function_call.arguments, str) else json.dumps(response.function_call.arguments)},
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id or f"call_{tool_name}_{iteration}",
                    "content": json.dumps(result),
                })
            else:
                messages.append({"role": "assistant", "content": response.content or "", "function_call": json.dumps({"name": tool_name, "arguments": response.function_call.arguments})})
                messages.append({"role": "function", "name": tool_name, "content": json.dumps(result)})

            has_all = all(_has_data_for_view(vid) for vid in view_ids) if view_ids else False
            if has_all and (views_data or view_images):
                break

        if not views_data and not view_images:
            if tool_calls_made:
                last = tool_calls_made[-1]
                if "error" in last.get("result", {}):
                    return {**state, "error": last["result"]["error"], "views_data": {}, "views_metadata": {}, "view_images": {}, "tool_calls": tool_calls_made}
            return {**state, "error": "No view data available. Ensure embedded capture completed or the view is visible.", "views_data": {}, "views_metadata": {}, "view_images": {}, "tool_calls": tool_calls_made}

        thought = f"Retrieved data for {len(views_data) + len(view_images)} view(s)" if (views_data or view_images) else "Retrieving view data..."
        return {
            **state,
            "views_data": views_data,
            "views_metadata": views_metadata,
            "view_images": view_images,
            "tool_calls": tool_calls_made,
            "current_thought": thought,
        }
    except Exception as e:
        logger.error(f"get_data_node error: {e}", exc_info=True)
        return {**state, "error": str(e), "views_data": {}, "views_metadata": {}, "view_images": {}}
