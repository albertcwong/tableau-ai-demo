"""Summarizer node for generating final summary."""
import logging
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState

MAX_DATA_ROWS = 50  # Limit rows per view to avoid token overflow
MAX_WORDS_CUSTOM = 300  # Hard limit for custom mode (failsafe if API ignores max_tokens)
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
            "detailed_analysis": None,
            "current_thought": None,
        }

    try:
        views_metadata = state.get("views_metadata", {})
        views_data = state.get("views_data", {})
        view_images = state.get("view_images", {}) or {}
        view_ids = state.get("context_views", [])

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
        if not v_data and state.get("view_data"):
            vd = state["view_data"]
            v_data = {"single": {"columns": vd.get("columns", []), "data": vd.get("data", []), "row_count": vd.get("row_count", 0)}}
        v_meta = views_metadata or {}
        if not v_meta and state.get("view_metadata"):
            v_meta = {"single": state.get("view_metadata", {})}
        view_data_str = _format_view_data(v_data, v_meta)
        if view_images and not v_data:
            view_data_str = "Dashboard images are attached below. Summarize the visualizations."
        elif view_images and v_data:
            view_data_str += "\n\nDashboard images are also attached below."
        
        # Format message history for prompt (last 10 messages)
        messages = state.get("messages", [])
        message_history_str = None
        if messages:
            # Take last 10 messages (user + assistant pairs)
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
        
        # Detect if user asked a specific question (for answer placement)
        user_query = state.get("user_query", "summarize this view")
        generic_phrases = ['summarize', 'summarize this view', 'summary', 'overview', 'brief summary']
        is_specific_question = (
            user_query and 
            (user_query.strip().lower() not in generic_phrases or 
             any(w in user_query.lower() for w in ['what', 'which', 'how', 'how much', 'how many', 'when', 'where', 'who', '?']))
        )
        
        prompt_vars = {
            "view_name": view_names,
            "row_count": total_row_count,
            "view_data": view_data_str,
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

        model = state.get("model", "gpt-4")
        provider = state.get("provider", "openai")
        has_vision = model and any(x in model.lower() for x in ["gpt-4o", "gpt-4-turbo", "gpt-5", "claude", "vision"])

        if view_images and not has_vision:
            return {
                **state,
                "error": "Image analysis requires a vision-capable model (e.g. gpt-4o, claude-3). Please switch model.",
                "final_answer": "Image analysis requires a vision-capable model.",
                "executive_summary": None,
                "detailed_analysis": None,
                "current_thought": None,
            }

        ai_client = UnifiedAIClient(gateway_url=settings.BACKEND_API_URL)

        if view_images and has_vision:
            user_content = [{"type": "text", "text": user_message + "\n\n" + view_data_str}]
            for view_id, b64 in view_images.items():
                name = views_metadata.get(view_id, {}).get("name", view_id)
                user_content.append({"type": "text", "text": f"\n[Image: {name}]"})
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
        else:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]

        apply_word_limit = is_specific_question or summary_mode == "brief"
        word_limit = MAX_WORDS_BRIEF if summary_mode == "brief" else MAX_WORDS_CUSTOM
        
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
        
        return {
            **state,
            "executive_summary": summary_text,
            "detailed_analysis": summary_text,
            "final_answer": summary_text,
            "current_thought": "Summarized view data and metrics."
        }
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        err_msg = str(e)
        return {
            **state,
            "error": f"Failed to generate summary: {err_msg}",
            "executive_summary": None,
            "detailed_analysis": None,
            "final_answer": f"Summary generation failed: {err_msg}"
        }
