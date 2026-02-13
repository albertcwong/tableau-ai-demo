"""Data fetcher node for retrieving view data from embedded_state only."""
import logging
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


def _sanitize_view_id(view_id: str) -> str:
    """Strip invalid suffixes (e.g. ,1:1) from view_id."""
    return view_id.split(",")[0].strip() if "," in view_id else view_id

def _extract_from_embedded(
    view_id: str,
    emb: Dict[str, Any],
    views_data: Dict[str, Any],
    views_metadata: Dict[str, Any],
) -> int:
    """Extract data from embedded_state into views_data/views_metadata. Returns rows added."""
    sheet_type = emb.get("sheet_type", "worksheet")
    active_sheet = emb.get("active_sheet", {})
    rows = 0

    if sheet_type == "worksheet" and "summary_data" in emb:
        sd = emb["summary_data"]
        views_data[view_id] = {
            "columns": sd.get("columns", []),
            "data": sd.get("data", []),
            "row_count": sd.get("row_count", 0),
        }
        name = active_sheet.get("name") or view_id
        views_metadata[view_id] = {"id": view_id, "name": name if name else view_id}
        return views_data[view_id]["row_count"]

    if sheet_type == "dashboard" and "sheets_data" in emb:
        for i, sheet in enumerate(emb["sheets_data"]):
            sheet_name = sheet.get("sheet_name", f"Sheet_{i}")
            sd = sheet.get("summary_data", {})
            key = f"{view_id}_sheet_{i}"
            views_data[key] = {
                "columns": sd.get("columns", []),
                "data": sd.get("data", []),
                "row_count": sd.get("row_count", 0),
            }
            views_metadata[key] = {"id": key, "name": sheet_name}
            rows += views_data[key]["row_count"]
        return rows

    return 0


@track_node_execution("summary", "data_fetcher")
async def fetch_data_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Fetch view data from embedded_state only. Requires views to be visible in the explorer
    so the Embedding API can capture their data.
    """
    try:
        view_ids = state.get("context_views", [])
        embedded_state = state.get("embedded_state") or {}

        if not view_ids:
            return {
                **state,
                "error": "No view in context. Please add a view first.",
                "view_data": None,
                "view_metadata": None,
                "views_data": {},
                "views_metadata": {},
            }

        logger.info(f"Fetching data for {len(view_ids)} view(s): {view_ids}")
        views_data: Dict[str, Any] = {}
        views_metadata: Dict[str, Any] = {}
        total_rows = 0
        successful_fetches = 0
        failed_views = []
        tool_calls = list(state.get("tool_calls", []))

        for view_id in view_ids:
            clean_view_id = _sanitize_view_id(view_id)
            emb = (
                embedded_state.get(view_id) or embedded_state.get(clean_view_id)
                if isinstance(embedded_state, dict)
                else None
            )

            if not emb:
                error_msg = f"View {view_id} not found in embedded_state. Ensure the view is visible in the explorer."
                logger.warning(error_msg)
                failed_views.append({"view_id": view_id, "error": "View not found in embedded_state"})
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "source": "embedded_state"},
                    "result": "error",
                    "error": error_msg,
                })
                continue

            # Check for capture errors
            if emb.get("capture_error"):
                error_msg = f"Capture failed for {view_id}: {emb.get('capture_error')}"
                logger.warning(error_msg)
                failed_views.append({"view_id": view_id, "error": emb.get("capture_error")})
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "source": "embedded_state"},
                    "result": "error",
                    "error": error_msg,
                })
                continue

            # Extract data from embedded_state
            rows = _extract_from_embedded(view_id, emb, views_data, views_metadata)
            if rows > 0:
                total_rows += rows
                successful_fetches += 1
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "source": "embedded_state"},
                    "result": f"success - {rows} rows (embedded)",
                })
            else:
                # Embedded state exists but has no data
                error_msg = f"View {view_id} has no summary_data or sheets_data. Ensure the view is visible and try again."
                logger.warning(error_msg)
                failed_views.append({"view_id": view_id, "error": "No data in embedded_state"})
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "source": "embedded_state"},
                    "result": "error",
                    "error": error_msg,
                })

        if successful_fetches == 0:
            error_details = "; ".join([f"{v['view_id']}: {v['error']}" for v in failed_views]) if failed_views else "No views captured"
            return {
                **state,
                "error": f"Could not get view data from embedded capture. {error_details}. Ensure the views are visible in the explorer and try again.",
                "view_data": None,
                "view_metadata": None,
                "views_data": {},
                "views_metadata": {},
                "tool_calls": tool_calls,
            }

        first_view_id = view_ids[0]
        primary_view_data = views_data.get(first_view_id)
        primary_view_metadata = views_metadata.get(first_view_id, {})

        # For dashboard embedded_state, first view may be a sheet key; use first available
        if not primary_view_data and views_data:
            first_key = next(iter(views_data))
            primary_view_data = views_data[first_key]
            primary_view_metadata = views_metadata.get(first_key, {})

        thought = f"Fetched data from {successful_fetches}/{len(view_ids)} view(s), total {total_rows} rows"
        if failed_views:
            thought += f" ({len(failed_views)} view(s) failed)"
        
        return {
            **state,
            "view_data": primary_view_data,
            "view_metadata": primary_view_metadata,
            "views_data": views_data,
            "views_metadata": views_metadata,
            "current_thought": thought,
            "tool_calls": tool_calls,
        }
    except Exception as e:
        logger.error(f"Error fetching view data: {e}", exc_info=True)
        view_ids = state.get("context_views", [])
        tool_calls = list(state.get("tool_calls", []))
        for view_id in view_ids:
            tool_calls.append({
                "tool": "get_view_data",
                "args": {"view_id": view_id, "source": "embedded_state"},
                "result": "error",
                "error": str(e),
            })
        return {
            **state,
            "error": f"Failed to fetch view data: {str(e)}",
            "view_data": None,
            "view_metadata": None,
            "views_data": {},
            "views_metadata": {},
            "tool_calls": tool_calls,
        }
