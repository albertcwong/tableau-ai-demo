"""Data fetcher node for retrieving view data from embedded_state, cache, or REST API fallback."""
import logging
from typing import Dict, Any, Optional

from langchain_core.runnables.config import ensure_config

from app.services.agents.summary.state import SummaryAgentState
from app.services.metrics import track_node_execution
from app.services.view_data_cache import get_cached, set_cached
from app.services.tableau.client import TableauClient

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
    Fetch view data from embedded_state or cache. If embedded_state is empty and cache is available,
    use cached data. If invalidate_cache is true and embedded_state is empty, return error.
    """
    try:
        view_ids = state.get("context_views", [])
        embedded_state = state.get("embedded_state") or {}
        conversation_id = state.get("conversation_id")
        invalidate_cache = state.get("invalidate_cache", False)

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
        used_cache = False

        # Check if we have embedded_state data for any views
        has_embedded_data = False
        for view_id in view_ids:
            clean_view_id = _sanitize_view_id(view_id)
            emb = (
                embedded_state.get(view_id) or embedded_state.get(clean_view_id)
                if isinstance(embedded_state, dict)
                else None
            )
            if emb and not emb.get("capture_error") and (emb.get("summary_data") or emb.get("sheets_data")):
                has_embedded_data = True
                break

        # Get tableau_client and max_rows from config (not state - state gets checkpointed and TableauClient isn't picklable)
        config = ensure_config()
        tableau_client: Optional[TableauClient] = config.get("configurable", {}).get("tableau_client")
        max_rows: int = config.get("configurable", {}).get("max_rows", 5000)
        
        # If invalidate_cache is true and no embedded_state, try REST fallback instead of error
        if invalidate_cache and not has_embedded_data:
            if tableau_client:
                logger.info(f"invalidate_cache=true but no embedded_state - using REST fallback for views {view_ids}")
                # Will fall through to REST fallback below
            else:
                error_msg = "View data may have changed. Please ensure the view is visible in the explorer and try again."
                logger.warning(f"invalidate_cache=true but no embedded_state and no tableau_client for views {view_ids}")
                return {
                    **state,
                    "error": error_msg,
                    "view_data": None,
                    "view_metadata": None,
                    "views_data": {},
                    "views_metadata": {},
                    "tool_calls": tool_calls,
                }

        # If no embedded_state data, try cache
        if not has_embedded_data and conversation_id:
            cached_result = get_cached(conversation_id, view_ids)
            if cached_result:
                cached_views_data, cached_views_metadata = cached_result
                views_data = cached_views_data.copy()
                views_metadata = cached_views_metadata.copy()
                total_rows = sum(v.get("row_count", 0) for v in views_data.values() if v)
                successful_fetches = len([v for v in views_data.values() if v])
                used_cache = True
                logger.info(f"Using cached view data for conversation {conversation_id}, views {view_ids}")
                for view_id in view_ids:
                    tool_calls.append({
                        "tool": "get_view_data",
                        "args": {"view_id": view_id, "source": "cache"},
                        "result": f"success - cached data ({views_data.get(view_id, {}).get('row_count', 0)} rows)",
                    })
        
        # REST API fallback: if no embedded_state and (no cache or cache miss), try REST
        if not has_embedded_data and tableau_client:
            # Check which views still need data
            views_to_fetch = []
            for view_id in view_ids:
                clean_view_id = _sanitize_view_id(view_id)
                # Skip if we already have data from cache or embedded_state
                if (view_id in views_data or clean_view_id in views_data):
                    continue
                views_to_fetch.append(view_id)
            
            if views_to_fetch:
                logger.info(f"Using REST API fallback for {len(views_to_fetch)} view(s): {views_to_fetch}")
                for view_id in views_to_fetch:
                    clean_view_id = _sanitize_view_id(view_id)
                    try:
                        # Try expanded first (for Dashboards), fallback to single view
                        expanded_result = await tableau_client.get_view_summary_expanded(
                            clean_view_id,
                            max_rows_per_view=max_rows
                        )
                        
                        if expanded_result["views"]:
                            # If multiple views (Dashboard), add each sheet
                            if len(expanded_result["views"]) > 1:
                                for i, view_data in enumerate(expanded_result["views"]):
                                    sheet_id = view_data["view_id"]
                                    sheet_name = view_data.get("name") or f"Sheet_{i}"
                                    key = f"{clean_view_id}_sheet_{i}"
                                    views_data[key] = {
                                        "columns": view_data["columns"],
                                        "data": view_data["data"],
                                        "row_count": view_data["row_count"],
                                    }
                                    views_metadata[key] = {"id": key, "name": sheet_name}
                                    total_rows += view_data["row_count"]
                                successful_fetches += 1
                                tool_calls.append({
                                    "tool": "get_view_data",
                                    "args": {"view_id": view_id, "source": "rest_api_expanded"},
                                    "result": f"success - {len(expanded_result['views'])} sheet(s), {expanded_result['total_rows']} rows (REST)",
                                })
                            else:
                                # Single view
                                view_data = expanded_result["views"][0]
                                views_data[clean_view_id] = {
                                    "columns": view_data["columns"],
                                    "data": view_data["data"],
                                    "row_count": view_data["row_count"],
                                }
                                views_metadata[clean_view_id] = {
                                    "id": clean_view_id,
                                    "name": view_data.get("name") or clean_view_id
                                }
                                total_rows += view_data["row_count"]
                                successful_fetches += 1
                                tool_calls.append({
                                    "tool": "get_view_data",
                                    "args": {"view_id": view_id, "source": "rest_api"},
                                    "result": f"success - {view_data['row_count']} rows (REST)",
                                })
                    except Exception as e:
                        error_msg = f"REST API fetch failed: {str(e)}"
                        logger.warning(f"Failed to fetch {view_id} via REST: {e}")
                        failed_views.append({"view_id": view_id, "error": error_msg})
                        tool_calls.append({
                            "tool": "get_view_data",
                            "args": {"view_id": view_id, "source": "rest_api"},
                            "result": "error",
                            "error": error_msg,
                        })
        
        # If still no data and no REST fallback available, mark as failed
        if not has_embedded_data and not used_cache and not tableau_client:
            for view_id in view_ids:
                clean_view_id = _sanitize_view_id(view_id)
                if clean_view_id not in views_data and view_id not in views_data:
                    error_msg = (
                        "No embedded_state, cache miss, and no REST fallback. "
                        "Select a Tableau connection in the explorer to enable server-side data fetch."
                    )
                    failed_views.append({"view_id": view_id, "error": error_msg})
                    tool_calls.append({
                        "tool": "get_view_data",
                        "args": {"view_id": view_id, "source": "embedded_state"},
                        "result": "error",
                        "error": error_msg,
                    })

        # Process embedded_state if available
        if has_embedded_data:
            for view_id in view_ids:
                clean_view_id = _sanitize_view_id(view_id)
                emb = (
                    embedded_state.get(view_id) or embedded_state.get(clean_view_id)
                    if isinstance(embedded_state, dict)
                    else None
                )

                if not emb:
                    # Skip if we already have cache data for this view
                    if used_cache and view_id in views_data:
                        continue
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
                    # Skip if we already have cache data for this view
                    if used_cache and view_id in views_data:
                        continue
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
                    if not (used_cache and view_id in views_data):
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
                "error": f"Could not get view data. {error_details}. Ensure the views are visible in the explorer and try again.",
                "view_data": None,
                "view_metadata": None,
                "views_data": {},
                "views_metadata": {},
                "tool_calls": tool_calls,
            }

        # Cache the data if we got it from embedded_state or REST API
        if (has_embedded_data or (tableau_client and successful_fetches > 0)) and conversation_id and views_data:
            set_cached(conversation_id, view_ids, views_data, views_metadata)

        first_view_id = view_ids[0]
        primary_view_data = views_data.get(first_view_id)
        primary_view_metadata = views_metadata.get(first_view_id, {})

        # For dashboard embedded_state, first view may be a sheet key; use first available
        if not primary_view_data and views_data:
            first_key = next(iter(views_data))
            primary_view_data = views_data[first_key]
            primary_view_metadata = views_metadata.get(first_key, {})

        thought = f"Fetched data from {successful_fetches}/{len(view_ids)} view(s), total {total_rows} rows"
        if used_cache:
            thought = f"Using cached view data from previous summary ({successful_fetches} view(s), {total_rows} rows)"
        elif tableau_client and successful_fetches > 0:
            thought = f"Fetched data via REST API ({successful_fetches} view(s), {total_rows} rows)"
        if failed_views:
            thought += f" ({len(failed_views)} view(s) failed)"
        
        first_view_id = view_ids[0]
        primary_view_data = views_data.get(first_view_id)
        primary_view_metadata = views_metadata.get(first_view_id, {})

        # For dashboard embedded_state, first view may be a sheet key; use first available
        if not primary_view_data and views_data:
            first_key = next(iter(views_data))
            primary_view_data = views_data[first_key]
            primary_view_metadata = views_metadata.get(first_key, {})
        
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
