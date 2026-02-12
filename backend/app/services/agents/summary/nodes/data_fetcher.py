"""Data fetcher node for retrieving view data."""
import logging
import re
from typing import Dict, Any, List, Optional

from langchain_core.runnables.config import ensure_config

from app.services.agents.summary.state import SummaryAgentState
from app.services.tableau.client import TableauClient
from app.services.cache import cached
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)

# Tableau internal IDs (e.g. param values) cause "Error parsing command parameter value string"
# Match patterns like (xxx,1:1) or xxx,1:1 anywhere in value
_RE_INTERNAL_ID = re.compile(r",\d+:\d+")


def _sanitize_view_id(view_id: str) -> str:
    """Strip invalid suffixes (e.g. ,1:1) from view_id - Tableau LUIDs are alphanumeric."""
    if "," in view_id:
        return view_id.split(",")[0].strip()
    return view_id


def _is_internal_filter_value(v: str) -> bool:
    """True if value looks like a Tableau internal ID that breaks vf_ params."""
    return bool(_RE_INTERNAL_ID.search(str(v)))


def _filters_from_embedded(filters: List[Dict]) -> Optional[Dict[str, str | List[str]]]:
    """Convert embedded filter list to vf_ param dict. Skips values that look like internal IDs."""
    if not filters:
        return None
    out: Dict[str, str | List[str]] = {}
    for f in filters:
        fn = f.get("fieldName")
        if not fn:
            continue
        vals = f.get("appliedValues")
        if vals:
            raw = [v.get("value", str(v)) for v in vals] if isinstance(vals[0], dict) else list(vals)
            cleaned = [str(v) for v in raw if not _is_internal_filter_value(str(v))]
            if cleaned:
                out[fn] = cleaned if len(cleaned) > 1 else cleaned[0]
        elif f.get("minValue") is not None or f.get("maxValue") is not None:
            minv, maxv = f.get("minValue"), f.get("maxValue")
            if minv is not None and maxv is not None:
                s = f"{minv},{maxv}"
                if not _is_internal_filter_value(s):
                    out[fn] = s
            elif minv is not None and not _is_internal_filter_value(str(minv)):
                out[fn] = str(minv)
            elif maxv is not None and not _is_internal_filter_value(str(maxv)):
                out[fn] = str(maxv)
    return out if out else None


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
        views_metadata[view_id] = {"id": view_id, "name": active_sheet.get("name", view_id)}
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


@cached("view_data", ttl_seconds=300)  # Cache view data for 5 minutes
async def _fetch_view_data_cached(
    view_id: str,
    max_rows: int = 1000,
    filters: Optional[Dict[str, str | List[str]]] = None,
) -> Dict[str, Any]:
    """Cached view data fetch function."""
    tableau_client = TableauClient()
    return await tableau_client.get_view_data(view_id, max_rows=max_rows, filters=filters)


@cached("view_metadata", ttl_seconds=600)  # Cache view metadata for 10 minutes
async def _fetch_view_metadata_cached(view_id: str) -> Dict[str, Any]:
    """Cached view metadata fetch function."""
    tableau_client = TableauClient()
    return await tableau_client.get_view(view_id)


@track_node_execution("summary", "data_fetcher")
async def fetch_data_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Fetch view data from Tableau.
    Uses embedded_state when present (filters, summary_data, sheets_data), else REST API.
    """
    try:
        view_ids = state.get("context_views", [])
        embedded_state = state.get("embedded_state") or {}

        if not view_ids:
            logger.warning("No view in context for data fetch")
            return {
                **state,
                "error": "No view in context. Please add a view first.",
                "view_data": None,
                "view_metadata": None,
                "views_data": {},
                "views_metadata": {},
            }

        logger.info(f"Fetching data for {len(view_ids)} view(s): {view_ids}")
        # Tableau client from config (not in state - not msgpack serializable)
        config = ensure_config()
        tableau_client = config.get("configurable", {}).get("tableau_client") or state.get("tableau_client")
        views_data: Dict[str, Any] = {}
        views_metadata: Dict[str, Any] = {}
        total_rows = 0
        successful_fetches = 0
        tool_calls = list(state.get("tool_calls", []))

        for view_id in view_ids:
            clean_view_id = _sanitize_view_id(view_id)
            emb = embedded_state.get(view_id) if isinstance(embedded_state, dict) else None

            # Use embedded data when available
            if emb and ("summary_data" in emb or "sheets_data" in emb):
                rows = _extract_from_embedded(view_id, emb, views_data, views_metadata)
                total_rows += rows
                successful_fetches += 1
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "source": "embedded_state"},
                    "result": f"success - {rows} rows (embedded)",
                })
                continue

            # Fallback: REST API with optional filters from embedded_state
            filters = None
            if emb and emb.get("filters"):
                filters = _filters_from_embedded(emb["filters"])
                if filters:
                    logger.info(f"Using filters for {view_id}: {list(filters.keys())}")

            if tableau_client:
                try:
                    view_data = await tableau_client.get_view_data(clean_view_id, max_rows=1000, filters=filters)
                    view_metadata = await tableau_client.get_view(clean_view_id)
                except Exception as e:
                    view_data = None
                    view_metadata = {"id": view_id, "name": view_id}
                    logger.error(f"Failed to fetch view data for {view_id}: {e}")
            else:
                view_data = await _fetch_view_data_cached(clean_view_id, max_rows=1000, filters=filters)
                view_metadata = await _fetch_view_metadata_cached(clean_view_id)

            if view_data:
                views_data[view_id] = view_data
                views_metadata[view_id] = view_metadata
                total_rows += view_data.get("row_count", 0)
                successful_fetches += 1
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "max_rows": 1000},
                    "result": f"success - {view_data.get('row_count', 0)} rows",
                })
            else:
                views_data[view_id] = None
                views_metadata[view_id] = {"id": view_id, "name": view_id}
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "max_rows": 1000},
                    "result": "error",
                    "error": "Failed to fetch data",
                })

        first_view_id = view_ids[0]
        primary_view_data = views_data.get(first_view_id)
        primary_view_metadata = views_metadata.get(first_view_id, {})

        # For dashboard embedded_state, first view may be a sheet key; use first available
        if not primary_view_data and views_data:
            first_key = next(iter(views_data))
            primary_view_data = views_data[first_key]
            primary_view_metadata = views_metadata.get(first_key, {})

        thought = f"Fetched data from {successful_fetches}/{len(view_ids)} view(s), total {total_rows} rows"
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
                "args": {"view_id": view_id, "max_rows": 1000},
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
