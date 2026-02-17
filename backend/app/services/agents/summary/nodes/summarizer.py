"""Summarizer node for generating final summary."""
import logging
from typing import Dict, Any, Set

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.tools import _sanitize_view_id

MAX_DATA_ROWS = 50  # Limit rows per view to avoid token overflow


def _key_belongs_to_image_view(key: str, view_images: Dict[str, str]) -> bool:
    """True if this views_data key belongs to a view that has an image (dashboard)."""
    if not view_images:
        return False
    base_id = key.split("_sheet_")[0] if "_sheet_" in key else key
    base_clean = _sanitize_view_id(base_id)
    return base_clean in view_images or any(_sanitize_view_id(k) == base_clean for k in view_images)


def _key_belongs_to_context(key: str, context_view_ids: list[str]) -> bool:
    """True if key is for a view in context (exact or sheet suffix)."""
    if not context_view_ids:
        return True
    clean_keys = {_sanitize_view_id(v) for v in context_view_ids}
    if key in clean_keys:
        return True
    for ck in clean_keys:
        if key.startswith(f"{ck}_sheet_"):
            return True
    return False
MAX_WORDS_BRIEF = 120  # Hard limit for brief mode (1-2 bullets per sheet, up to 120 words)


def _format_view_data(views_data: Dict[str, Any], views_metadata: Dict[str, Any]) -> str:
    """Format views_data with per-sheet traceability: sheet name, row count, columns."""
    if not views_data:
        return "(No view data available)"
    parts = []
    sheet_summaries = []
    for view_id, v_data in views_data.items():
        if not v_data:
            continue
        cols = v_data.get("columns", [])
        rows = v_data.get("data", [])[:MAX_DATA_ROWS]
        meta = views_metadata.get(view_id, {})
        name = meta.get("name") or meta.get("id") or view_id
        row_count = v_data.get("row_count", 0)
        col_str = ", ".join(str(c) for c in cols) if cols else "(none)"
        sheet_summaries.append(f'- {name}: {row_count} rows, columns: {col_str}')
        if not cols:
            parts.append(f"**{name}** (no columns)")
            continue
        header = " | ".join(str(c) for c in cols)
        sep = " | ".join(["---"] * len(cols))
        table_lines = [f"**{name}** ({row_count} rows)", "", f"| {header} |", f"| {sep} |"]
        for row in rows:
            vals = [str(v)[:50] if v is not None else "" for v in (row if isinstance(row, (list, tuple)) else [row])]
            if len(vals) < len(cols):
                vals.extend([""] * (len(cols) - len(vals)))
            elif len(vals) > len(cols):
                vals = vals[:len(cols)]
            table_lines.append("| " + " | ".join(vals) + " |")
        parts.append("\n".join(table_lines))
    header_block = "\n".join(sheet_summaries) + f"\nTotal: {sum(v.get('row_count', 0) for v in views_data.values() if v)} rows across {len(sheet_summaries)} sheet(s)"
    return header_block + "\n\n## Data Tables\n\n" + ("\n\n".join(parts) if parts else "(No data)")
from app.prompts.registry import prompt_registry
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


async def summarize_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Generate final natural language summary from view data only.
    """
    if state.get("error"):
        return {
            **state,
            "final_answer": state["error"],
            "executive_summary": None,
            "step_metadata": None,
            "detailed_analysis": None,
            "current_thought": None,
        }

    try:
        views_metadata = state.get("views_metadata", {})
        views_data = state.get("views_data", {}) or {}
        view_images = state.get("view_images", {}) or {}
        view_ids = state.get("context_views", [])

        # Only use data for views in context - prevents wrong-view data from leaking in
        orig_data_keys = set(views_data.keys())
        orig_img_keys = set(view_images.keys())
        views_data = {k: v for k, v in views_data.items() if _key_belongs_to_context(k, view_ids)}
        view_images = {k: v for k, v in view_images.items() if _key_belongs_to_context(k, view_ids)}
        dropped = (orig_data_keys - set(views_data.keys())) | (orig_img_keys - set(view_images.keys()))
        if dropped:
            logger.info(f"Summarizer: filtered out data not in context_views={view_ids}: dropped_keys={dropped}")
        logger.info(f"Summarizer START: views_data_keys={list(views_data.keys())} view_images_keys={list(view_images.keys())} context_views={view_ids}")

        view_info_list = []
        total_row_count = 0

        if views_metadata and (views_data or view_images):
            for view_id in set(list(views_data.keys()) + list(view_images.keys())):
                v_metadata = views_metadata.get(view_id, {})
                view_name = v_metadata.get("name") or v_metadata.get("id") or view_id or "Unknown View"
                if view_id in view_images:
                    view_info_list.append({"id": view_id, "name": view_name, "row_count": 0, "type": "image"})
                else:
                    v_data = views_data.get(view_id)
                    if not v_data:
                        continue
                    row_count = v_data.get("row_count", 0)
                    total_row_count += row_count
                    view_info_list.append({"id": view_id, "name": view_name, "row_count": row_count, "type": "tabular"})
        else:
            # Single view (backward compatibility)
            view_metadata = state.get("view_metadata") or {}
            view_data = state.get("view_data") or {}
            view_name = view_metadata.get("name") or view_metadata.get("id") or (view_ids[0] if view_ids else "Unknown View")
            row_count = view_data.get("row_count", 0)
            total_row_count = row_count
            view_info_list.append({
                "id": view_ids[0] if view_ids else "unknown",
                "name": view_name,
                "row_count": row_count
            })
        
        # Format view names for prompt
        if len(view_info_list) > 1:
            view_names = ", ".join([v["name"] for v in view_info_list])
            view_count_text = f"{len(view_info_list)} views"
        else:
            view_names = view_info_list[0]["name"] if view_info_list else (view_ids[0] if view_ids else "Unknown View")
            view_count_text = "1 view"
        
        summary_mode = state.get("summary_mode") or "full"
        v_data = views_data or {}
        v_meta = views_metadata or {}
        # Exclude tabular data for views that have images (dashboards)—image is source of truth for those
        v_data_tabular = {k: v for k, v in v_data.items() if not _key_belongs_to_image_view(k, view_images)}
        logger.info(f"Summarizer: v_data_keys={list(v_data.keys())} v_data_tabular_keys={list(v_data_tabular.keys())} view_images_keys={list(view_images.keys())}")
        view_data_str = _format_view_data(v_data_tabular, v_meta)
        if view_images and not v_data_tabular:
            view_data_str = (
                "Dashboard images are attached below. "
                "CRITICAL: Describe ONLY what is visible in these images. "
                "Do NOT use metrics or numbers from conversation history—they may refer to different views."
            )
        elif view_images and v_data_tabular:
            view_data_str += "\n\nDashboard images are also attached below."
        logger.info(f"Summarizer: has_tabular={bool(v_data_tabular)} has_images={bool(view_images)} view_data_str[:200]={view_data_str[:200]}")
        
        # Format message history for prompt (last 10 messages)
        messages = state.get("messages", [])
        message_history_str = None
        if messages:
            recent_messages = messages[-10:]
            history_lines = []
            for msg in recent_messages:
                role = msg.get("role", "unknown") if isinstance(msg, dict) else "unknown"
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                if role in ("user", "assistant"):
                    role_label = "User" if role == "user" else "Assistant"
                    history_lines.append(f"{role_label}: {content}")
            if history_lines:
                message_history_str = "\n".join(history_lines)
                logger.info(f"Summarizer: including message_history with {len(recent_messages)} messages, total_chars={len(message_history_str)}")
        
        # Detect if user asked a specific question (for answer placement)
        user_query = state.get("user_query", "summarize this view")
        generic_phrases = ['summarize', 'summarize this view', 'summary', 'overview', 'brief summary']
        is_specific_question = (
            user_query and 
            (user_query.strip().lower() not in generic_phrases or 
             any(w in user_query.lower() for w in ['what', 'which', 'how', 'how much', 'how many', 'when', 'where', 'who', '?']))
        )
        
        has_tabular = bool(v_data_tabular)
        has_images = bool(view_images)
        prompt_vars = {
            "view_name": view_names,
            "row_count": total_row_count,
            "view_data": view_data_str,
            "image_only": has_images and not has_tabular,
            "mixed_views": has_images and has_tabular,
            "insights": state.get("key_insights", []),
            "recommendations": state.get("recommendations", []),
            "user_query": user_query,
            "message_history": message_history_str or "",
            "is_specific_question": is_specific_question
        }
        # When user typed their own question (not Brief/Full buttons), use custom template for concise answer
        if is_specific_question:
            template_file = "agents/summary/final_summary_custom.txt"
            user_message = state.get("user_query", "summarize this view")
        elif summary_mode == "brief":
            template_file = "agents/summary/final_summary_brief.txt"
            user_message = "Generate a concise executive summary. For each sheet: use the sheet name as a title on its own line, then 1-2 relevant bullet points. Total limit: 120 words."
        elif summary_mode == "custom":
            template_file = "agents/summary/final_summary_custom.txt"
            user_message = state.get("user_query", "summarize this view")
        else:
            template_file = "agents/summary/final_summary.txt"
            user_message = f"Generate executive summary and detailed analysis for {view_count_text}: {view_names}." if len(view_info_list) > 1 else "Generate executive summary and detailed analysis."
        
        system_prompt = prompt_registry.get_prompt(template_file, variables=prompt_vars)
        logger.info(f"Summarizer: system_prompt_len={len(system_prompt)}, contains_data={'Data Tables' in system_prompt or 'row_count' in system_prompt}")
        if "Data Tables" in system_prompt or ("row" in system_prompt and "columns" in system_prompt):
            logger.warning(f"Summarizer: system prompt may contain tabular data! Checking view_data section...")
            # Log a sample to see what's in there
            if "## View Data" in system_prompt:
                start = system_prompt.find("## View Data")
                end = system_prompt.find("## User Query", start) if "## User Query" in system_prompt else start + 500
                logger.warning(f"View Data section: {system_prompt[start:end]}")

        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")

        ai_client = UnifiedAIClient(gateway_url=settings.BACKEND_API_URL)

        if view_images:
            user_content = [{"type": "text", "text": user_message + "\n\n" + view_data_str}]
            for view_id, b64 in view_images.items():
                name = views_metadata.get(view_id, {}).get("name", view_id)
                user_content.append({"type": "text", "text": f"\n[Image: {name}]"})
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
                logger.info(f"Summarizer: adding image for view {view_id} (name={name}, b64_len={len(b64)}, b64_preview={b64[:100]}...)")
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
            logger.info(f"Summarizer: sending {len(view_images)} images, user_text={user_message[:80]}...")
        else:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
            logger.info(f"Summarizer: sending tabular only, user_message={user_message}")

        apply_word_limit = summary_mode == "brief"
        word_limit = MAX_WORDS_BRIEF
        
        response = await ai_client.chat(
            model=model,
            provider=provider,
            messages=messages
        )
        
        summary_text = (response.content or "").strip()
        if not summary_text:
            raise ValueError("AI returned empty response")
        # Failsafe: truncate if API ignored max_tokens
        if apply_word_limit:
            words = summary_text.split()
            if len(words) > word_limit:
                summary_text = " ".join(words[:word_limit]) + "..."
                logger.warning(f"Summarizer: truncated response from {len(words)} to {word_limit} words (API may have ignored max_tokens)")
        
        view_names = ", ".join(v["name"] for v in view_info_list) if view_info_list else "view"
        return {
            **state,
            "executive_summary": summary_text,
            "detailed_analysis": summary_text,
            "final_answer": summary_text,
            "current_thought": f"Summarized {view_names}.",
            "step_metadata": None,  # Clear get_data's metadata so it doesn't appear under this step
        }
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        err_msg = str(e)
        return {
            **state,
            "error": f"Failed to generate summary: {err_msg}",
            "executive_summary": None,
            "detailed_analysis": None,
            "final_answer": f"Summary generation failed: {err_msg}",
            "step_metadata": None,
        }
