"""Tool definitions for Summary agent get_data node."""
import base64
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


def _sanitize_view_id(view_id: str) -> str:
    return view_id.split(",")[0].strip() if "," in view_id else view_id


def _extract_from_embedded(
    view_id: str,
    emb: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract data from embedded_state. Returns single-sheet dict or error."""
    sheet_type = emb.get("sheet_type", "worksheet")
    active_sheet = emb.get("active_sheet", {})
    if sheet_type == "worksheet" and "summary_data" in emb:
        sd = emb["summary_data"]
        return {
            "columns": sd.get("columns", []),
            "data": sd.get("data", []),
            "row_count": sd.get("row_count", 0),
            "name": active_sheet.get("name") or view_id,
        }
    if sheet_type == "dashboard" and "sheets_data" in emb:
        all_cols, all_data, total = [], [], 0
        for i, sheet in enumerate(emb["sheets_data"]):
            sd = sheet.get("summary_data", {})
            cols = sd.get("columns", [])
            data = sd.get("data", [])
            total += len(data)
            if cols and data:
                all_cols = cols
                all_data.extend(data)
        return {
            "columns": all_cols,
            "data": all_data,
            "row_count": total,
            "name": active_sheet.get("name") or view_id,
        }
    return {"error": "No summary_data or sheets_data in embedded state"}


def _extract_embedded_to_views_data(
    view_id: str, emb: Dict[str, Any]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Extract embedded_state into views_data and views_metadata. Returns (views_data, views_metadata)."""
    clean = _sanitize_view_id(view_id)
    views_data: Dict[str, Dict[str, Any]] = {}
    views_metadata: Dict[str, Dict[str, Any]] = {}
    sheet_type = emb.get("sheet_type", "worksheet")
    active_sheet = emb.get("active_sheet", {})

    if sheet_type == "worksheet" and "summary_data" in emb:
        sd = emb["summary_data"]
        views_data[clean] = {"columns": sd.get("columns", []), "data": sd.get("data", []), "row_count": sd.get("row_count", 0)}
        views_metadata[clean] = {"id": clean, "name": active_sheet.get("name") or clean}
        return views_data, views_metadata

    if sheet_type == "dashboard" and "sheets_data" in emb:
        for i, sheet in enumerate(emb["sheets_data"]):
            sheet_name = sheet.get("sheet_name", f"Sheet_{i}")
            sd = sheet.get("summary_data", {})
            key = f"{clean}_sheet_{i}"
            views_data[key] = {"columns": sd.get("columns", []), "data": sd.get("data", []), "row_count": sd.get("row_count", 0)}
            views_metadata[key] = {"id": key, "name": sheet_name}
        return views_data, views_metadata

    return views_data, views_metadata


class SummaryTools:
    """Tools for Summary agent: get_embed_data, get_rest_summary_data, get_exported_image, query_view_metadata."""

    def __init__(
        self,
        embedded_state: Dict[str, Any],
        view_ids: List[str],
        tableau_client: Optional[TableauClient] = None,
    ):
        self.embedded_state = embedded_state or {}
        self.view_ids = view_ids or []
        self.tableau_client = tableau_client

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_embed_data",
                "description": "Get tabular data from embedded view (Embedding API). Use ONLY for views RENDERED ON CANVAS (in embedded_state). Works for both worksheets and dashboards.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "view_id": {"type": "string", "description": "View ID (LUID)"},
                    },
                    "required": ["view_id"],
                },
            },
            {
                "name": "query_view_metadata",
                "description": "Get view type (worksheet or dashboard) and name. Use ONLY when view is NOT on canvas to decide REST tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "view_id": {"type": "string", "description": "View ID (LUID)"},
                    },
                    "required": ["view_id"],
                },
            },
            {
                "name": "get_rest_summary_data",
                "description": "Get tabular data via REST API. Use for SHEETS not on canvas (after query_view_metadata returns worksheet).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "view_id": {"type": "string", "description": "View ID (LUID)"},
                    },
                    "required": ["view_id"],
                },
            },
            {
                "name": "get_exported_image",
                "description": "Get PNG image of view via REST API. Use for DASHBOARDS not on canvas (after query_view_metadata returns dashboard).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "view_id": {"type": "string", "description": "View ID (LUID)"},
                        "width": {"type": "integer", "description": "Optional width in pixels"},
                        "height": {"type": "integer", "description": "Optional height in pixels"},
                    },
                    "required": ["view_id"],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        view_id = arguments.get("view_id", "")
        if not view_id:
            return {"error": "view_id is required"}
        clean_id = _sanitize_view_id(view_id)
        if view_id not in self.view_ids and clean_id not in self.view_ids:
            return {"error": f"View {view_id} not in context. Available: {self.view_ids}"}

        if tool_name == "query_view_metadata":
            return await self._query_view_metadata(clean_id)
        if tool_name == "get_embed_data":
            return self._get_embed_data(view_id, clean_id)
        if tool_name == "get_rest_summary_data":
            return await self._get_rest_summary_data(clean_id)
        if tool_name == "get_exported_image":
            return await self._get_exported_image(
                clean_id,
                arguments.get("width"),
                arguments.get("height"),
            )
        return {"error": f"Unknown tool: {tool_name}"}

    async def _query_view_metadata(self, view_id: str) -> Dict[str, Any]:
        if not self.tableau_client:
            return {"error": "No Tableau connection. Select a connection in the explorer."}
        try:
            return await self.tableau_client.get_view_type(view_id)
        except Exception as e:
            logger.warning(f"query_view_metadata failed: {e}")
            return {"error": str(e)}

    def _get_embed_data(self, view_id: str, clean_id: str) -> Dict[str, Any]:
        emb = self.embedded_state.get(view_id) or self.embedded_state.get(clean_id)
        if not emb:
            return {"error": f"View {view_id} not in embedded_state. Ensure the view is visible in the explorer."}
        if emb.get("capture_error"):
            return {"error": f"Capture failed: {emb.get('capture_error')}"}
        vd, vm = _extract_embedded_to_views_data(view_id, emb)
        if not vd:
            return {"error": "No summary_data or sheets_data in embedded state"}
        if len(vd) == 1:
            k = next(iter(vd))
            d = vd[k]
            return {"columns": d["columns"], "data": d["data"], "row_count": d["row_count"], "name": vm.get(k, {}).get("name", k)}
        return {"sheets": {k: {**vd[k], "name": vm.get(k, {}).get("name", k)} for k in vd}}

    async def _get_rest_summary_data(self, view_id: str) -> Dict[str, Any]:
        if not self.tableau_client:
            return {"error": "No Tableau connection. Select a connection in the explorer."}
        try:
            result = await self.tableau_client.get_view_summary_expanded(view_id, max_rows_per_view=5000)
            views = result.get("views", [])
            if not views:
                return {"error": "No data returned from REST API"}
            if len(views) == 1:
                v = views[0]
                return {"columns": v.get("columns", []), "data": v.get("data", []), "row_count": v.get("row_count", 0), "name": v.get("name", view_id)}
            sheets = {}
            for i, v in enumerate(views):
                key = f"{view_id}_sheet_{i}"
                sheets[key] = {"columns": v.get("columns", []), "data": v.get("data", []), "row_count": v.get("row_count", 0), "name": v.get("name", key)}
            return {"sheets": sheets}
        except Exception as e:
            logger.warning(f"get_rest_summary_data failed: {e}")
            return {"error": str(e)}

    async def _get_exported_image(
        self, view_id: str, width: Optional[int], height: Optional[int]
    ) -> Dict[str, Any]:
        if not self.tableau_client:
            return {"error": "No Tableau connection. Select a connection in the explorer."}
        try:
            png_bytes = await self.tableau_client.get_view_image(view_id, width=width, height=height)
            b64 = base64.b64encode(png_bytes).decode("utf-8")
            return {"image_base64": b64, "format": "png"}
        except Exception as e:
            logger.warning(f"get_exported_image failed: {e}")
            return {"error": str(e)}
