"""Get data node using tool calls for Summary agent."""
import json
import logging
from typing import Dict, Any, Optional

from langchain_core.runnables.config import ensure_config

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.tools import SummaryTools, _extract_embedded_to_views_data, _sanitize_view_id
from app.services.ai.client import UnifiedAIClient
from app.prompts.registry import prompt_registry
from app.core.config import settings
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


PREVIEW_ROWS = 8  # Rows to include in data_preview for debugging


def _build_data_thought(
    views_data: Dict[str, Any],
    views_metadata: Dict[str, Any],
    view_images: Dict[str, str],
    source: str,
    tool_calls: Optional[list] = None,
) -> tuple:
    """Build detailed reasoning text and data_summary for UI. Returns (thought_str, data_summary_dict)."""
    parts = []
    data_summary = {"views": [], "source": source, "tool_calls": [], "data_preview": []}
    if tool_calls:
        def _view_id(tc):
            a = tc.get("arguments")
            return a.get("view_id") if isinstance(a, dict) else None
        data_summary["tool_calls"] = [{"tool": tc.get("tool"), "view_id": _view_id(tc)} for tc in tool_calls]

    # Tabular data + sample rows for debugging
    for view_id, v_data in (views_data or {}).items():
        if not v_data:
            continue
        meta = views_metadata.get(view_id, {})
        name = meta.get("name") or meta.get("id") or view_id
        cols = v_data.get("columns", [])
        rows = v_data.get("data", [])
        row_count = v_data.get("row_count", 0)
        col_preview = ", ".join(str(c) for c in cols[:6]) if cols else "(none)"
        if len(cols) > 6:
            col_preview += f", +{len(cols) - 6} more"
        parts.append(f"{name}: {row_count} rows, columns: [{col_preview}]")
        data_summary["views"].append({"id": view_id, "name": name, "row_count": row_count, "columns": cols, "type": "tabular"})
        # Include sample rows so user can see exactly what data was sent
        preview_rows = (rows if isinstance(rows, list) else [])[:PREVIEW_ROWS]
        data_summary["data_preview"].append({"id": view_id, "name": name, "columns": cols, "rows": preview_rows})

    # Image data (dashboards)
    for view_id, _ in (view_images or {}).items():
        meta = views_metadata.get(view_id, {})
        name = meta.get("name") or meta.get("id") or view_id
        parts.append(f"{name}: dashboard image")
        data_summary["views"].append({"id": view_id, "name": name, "type": "image"})

    if not parts:
        thought = "No view data retrieved."
    else:
        source_label = "embedded state" if source == "embedded" else "REST API" if source == "REST" else "tools"
        thought = f"Pulled data for {len(parts)} view(s) from {source_label}. " + "; ".join(parts)
    return thought, data_summary


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
                "current_thought": "No view in context. Add a view to summarize.",
                "step_metadata": {"data_summary": {"views": [], "source": None}},
            }

        emb_status = {k: {"has_data": bool(v.get("summary_data") or v.get("sheets_data")), "capture_error": v.get("capture_error")} for k, v in (embedded_state or {}).items()}
        logger.info(f"get_data START view_ids={view_ids} embedded_keys={list(embedded_state.keys())} emb_status={emb_status}")

        # Include embedded_state keys for tool validation
        all_view_ids = list(set(view_ids + [_sanitize_view_id(k) for k in embedded_state]))

        config = ensure_config()
        tableau_client = config.get("configurable", {}).get("tableau_client")
        if not tableau_client and view_ids:
            try:
                tableau_client = TableauClient()
                await tableau_client._ensure_authenticated()
                logger.info("get_data tableau_client created")
            except Exception as e:
                logger.warning(f"TableauClient init failed: {e}")
        logger.info(f"get_data tableau_client={'present' if tableau_client else 'MISSING'}")

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
        logger.info(f"get_data after_embedded views_data_keys={list(views_data.keys())} views_needing_data={views_needing_data}")
        if not views_needing_data:
            # Always fetch images for display in reasoning steps (embedded capture has no screenshots)
            if tableau_client:
                for vid in view_ids:
                    cid = _sanitize_view_id(vid)
                    if cid not in view_images:
                        try:
                            res = await tools._get_exported_image(cid, None, None)  # Full resolution for better summaries
                            if "error" not in res and res.get("image_base64"):
                                view_images[cid] = res["image_base64"]
                                if cid not in views_metadata:
                                    meta = await tools._query_view_metadata(cid)
                                    views_metadata[cid] = {"id": cid, "name": meta.get("name", cid)}
                                logger.info(f"get_data embedded: fetched image for {cid} ({len(res['image_base64'])} b64 chars)")
                            else:
                                logger.info(f"get_data embedded: no image for {cid} error={res.get('error')}")
                        except Exception as e:
                            logger.warning(f"get_data image fetch for {vid}: {e}")
            thought, data_summary = _build_data_thought(views_data, views_metadata, view_images, source="embedded")
            sm = {"tool_calls": [], "data_summary": data_summary}
            if view_images:
                sm["view_images"] = [{"id": vid, "name": views_metadata.get(vid, {}).get("name", vid), "base64": b64} for vid, b64 in view_images.items()]
            return {**state, "views_data": views_data, "views_metadata": views_metadata, "view_images": view_images, "current_thought": thought, "step_metadata": sm}

        # Views not on canvas or capture failed: fetch via REST (per rest_api_view_summary_fallback)
        def _not_on_canvas(vid: str) -> bool:
            emb = embedded_state.get(vid) or embedded_state.get(_sanitize_view_id(vid))
            return not emb or bool(emb.get("capture_error"))

        rest_candidates = [v for v in views_needing_data if _not_on_canvas(v)]
        logger.info(f"get_data REST_fallback candidates={rest_candidates} tableau_client={'yes' if tableau_client else 'no'}")
        for vid in rest_candidates:
            if not tableau_client:
                logger.info("get_data REST_fallback skipped: no tableau_client")
                break
            cid = _sanitize_view_id(vid)
            try:
                meta = await tools._query_view_metadata(cid)
                logger.info(f"get_data REST_fallback {vid} query_view_metadata={meta}")
                if "error" in meta:
                    logger.info(f"get_data REST_fallback {vid} meta error, skip")
                    continue
                vt = meta.get("view_type", "worksheet")
                if vt == "dashboard":
                    res = await tools._get_exported_image(cid, None, None)
                    logger.info(f"get_data REST_fallback {vid} get_exported_image has_error={bool(res.get('error'))} has_b64={bool(res.get('image_base64'))}")
                    if "error" not in res and res.get("image_base64"):
                        view_images[cid] = res["image_base64"]
                        md = {"id": cid, "name": meta.get("name", cid)}
                        if meta.get("sheet_names"):
                            md["sheet_names"] = meta["sheet_names"]
                        views_metadata[cid] = views_metadata.get(cid) or md
                else:
                    res = await tools._get_rest_summary_data(cid)
                    logger.info(f"get_data REST_fallback {vid} get_rest_summary_data has_error={bool(res.get('error'))} has_sheets={bool(res.get('sheets'))} has_data={bool(res.get('data'))}")
                    if "error" not in res:
                        if "sheets" in res:
                            for k, d in res["sheets"].items():
                                views_data[k] = {"columns": d.get("columns", []), "data": d.get("data", []), "row_count": d.get("row_count", 0)}
                                views_metadata[k] = {"id": k, "name": d.get("name", k)}
                        else:
                            views_data[cid] = {"columns": res.get("columns", []), "data": res.get("data", []), "row_count": res.get("row_count", 0)}
                            views_metadata[cid] = {"id": cid, "name": res.get("name", cid)}
                logger.info(f"REST fallback for {vid} ({vt})")
            except Exception as e:
                logger.warning(f"REST fallback failed for {vid}: {e}")
        views_needing_data = [v for v in views_needing_data if not _has_data_for_view(v)]
        logger.info(f"get_data after_REST views_data_keys={list(views_data.keys())} view_images_keys={list(view_images.keys())} views_needing_data={views_needing_data}")
        if not views_needing_data:
            thought, data_summary = _build_data_thought(views_data, views_metadata, view_images, source="REST")
            sm = {"tool_calls": [], "data_summary": data_summary}
            if view_images:
                view_imgs_list = [{"id": vid, "name": views_metadata.get(vid, {}).get("name", vid), "base64": b64} for vid, b64 in view_images.items()]
                sm["view_images"] = view_imgs_list
                logger.info(f"get_data: adding view_images to step_metadata count={len(view_imgs_list)} ids={[v['id'] for v in view_imgs_list]} base64_lengths={[len(v['base64']) for v in view_imgs_list]}")
            else:
                logger.info(f"get_data: NO view_images to add (view_images dict is empty)")
            return {**state, "views_data": views_data, "views_metadata": views_metadata, "view_images": view_images, "current_thought": thought, "step_metadata": sm}

        logger.info(f"get_data entering LLM loop for views_needing_data={views_needing_data}")
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
        use_tools_format = model and any(x in model.lower() for x in ["gpt-4o", "gpt-4-turbo", "gpt-5", "o1", "o3", "claude", "endor", "gemini"])
        tool_defs = tools.get_tool_definitions()
        tools_payload = [{"type": "function", "function": f} for f in tool_defs] if use_tools_format else tool_defs

        ai_client = UnifiedAIClient(gateway_url=settings.BACKEND_API_URL, timeout=120)
        tool_calls_made = []
        iteration = 0

        def _msg_summary(msgs):
            return [{"role": m.get("role"), "len": len(str(m.get("content", ""))), "has_tc": bool(m.get("tool_calls")), "has_fc": bool(m.get("function_call"))} for m in msgs]

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info(f"get_data iter={iteration} provider={provider} model={model} use_tools={use_tools_format} msgs={_msg_summary(messages)}")
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
                logger.error(f"get_data iter={iteration} LLM call failed: {e}", exc_info=True)
                return {**state, "error": str(e), "views_data": views_data, "views_metadata": views_metadata, "view_images": view_images}

            if not response.function_call:
                logger.info(f"get_data iter={iteration} LLM returned NO function_call, breaking")
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
            logger.info(f"get_data iter={iteration} tool={tool_name} view_id={view_id} has_error={bool(result.get('error'))}")

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
                logger.info(f"get_data iter={iteration} has_all=True, breaking")
                break

        logger.info(f"get_data EXIT iter={iteration} views_data={bool(views_data)} view_images={bool(view_images)} tool_calls_count={len(tool_calls_made)}")
        thought, data_summary = _build_data_thought(views_data, views_metadata, view_images, source="tools", tool_calls=tool_calls_made)
        step_metadata = {"tool_calls": tool_calls_made, "data_summary": data_summary}
        if view_images:
            step_metadata["view_images"] = [{"id": vid, "name": views_metadata.get(vid, {}).get("name", vid), "base64": b64} for vid, b64 in view_images.items()]
        if not views_data and not view_images:
            if tool_calls_made:
                last = tool_calls_made[-1]
                if "error" in last.get("result", {}):
                    logger.info(f"get_data returning last_tool_error: {last['result']['error']}")
                    return {**state, "error": last["result"]["error"], "views_data": {}, "views_metadata": {}, "view_images": {}, "tool_calls": tool_calls_made, "current_thought": thought, "step_metadata": step_metadata}
            logger.info("get_data returning generic 'No view data' (no tool_calls or last had no error)")
            return {**state, "error": "No view data available. Ensure embedded capture completed or the view is visible.", "views_data": {}, "views_metadata": {}, "view_images": {}, "tool_calls": tool_calls_made, "current_thought": thought, "step_metadata": step_metadata}

        return {
            **state,
            "views_data": views_data,
            "views_metadata": views_metadata,
            "view_images": view_images,
            "tool_calls": tool_calls_made,
            "current_thought": thought,
            "step_metadata": step_metadata,
        }
    except Exception as e:
        logger.error(f"get_data_node error: {e}", exc_info=True)
        return {**state, "error": str(e), "views_data": {}, "views_metadata": {}, "view_images": {}}
