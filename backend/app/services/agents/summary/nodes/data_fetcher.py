"""Data fetcher node for retrieving view data."""
import logging
import asyncio
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState
from app.services.tableau.client import TableauClient
from app.services.cache import cached
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@cached("view_data", ttl_seconds=300)  # Cache view data for 5 minutes
async def _fetch_view_data_cached(view_id: str, max_rows: int = 1000) -> Dict[str, Any]:
    """Cached view data fetch function."""
    tableau_client = TableauClient()
    return await tableau_client.get_view_data(view_id, max_rows=max_rows)


@cached("view_metadata", ttl_seconds=600)  # Cache view metadata for 10 minutes
async def _fetch_view_metadata_cached(view_id: str) -> Dict[str, Any]:
    """Cached view metadata fetch function."""
    tableau_client = TableauClient()
    return await tableau_client.get_view(view_id)


@track_node_execution("summary", "data_fetcher")
async def fetch_data_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Fetch view data from Tableau.
    
    This is an "Act" step in ReAct.
    Uses caching to avoid repeated API calls.
    """
    try:
        view_ids = state.get("context_views", [])
        
        if not view_ids:
            logger.warning("No view in context for data fetch")
            return {
                **state,
                "error": "No view in context. Please add a view first.",
                "view_data": None,
                "view_metadata": None
            }
        
        # Use first view
        view_id = view_ids[0]
        
        logger.info(f"Fetching data for view: {view_id}")
        
        # Fetch view data and metadata in parallel for better performance
        try:
            view_data_task = _fetch_view_data_cached(view_id, max_rows=1000)
            view_metadata_task = _fetch_view_metadata_cached(view_id)
            
            # Execute in parallel
            view_data, view_metadata = await asyncio.gather(
                view_data_task,
                view_metadata_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(view_data, Exception):
                logger.error(f"Failed to fetch view data: {view_data}")
                return {
                    **state,
                    "error": f"Failed to fetch view data: {str(view_data)}",
                    "view_data": None,
                    "view_metadata": None
                }
            
            if isinstance(view_metadata, Exception):
                logger.warning(f"Failed to fetch view metadata: {view_metadata}")
                view_metadata = {"id": view_id, "name": view_id}
        except Exception as e:
            logger.error(f"Error in parallel fetch: {e}", exc_info=True)
            # Fallback to sequential fetch
            view_data = await _fetch_view_data_cached(view_id, max_rows=1000)
            try:
                view_metadata = await _fetch_view_metadata_cached(view_id)
            except Exception as meta_error:
                logger.warning(f"Failed to fetch view metadata: {meta_error}")
                view_metadata = {"id": view_id, "name": view_id}
        
        return {
            **state,
            "view_data": view_data,
            "view_metadata": view_metadata,
            "current_thought": f"Fetched {view_data.get('row_count', 0)} rows from view",
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_view_data",
                "args": {"view_id": view_id, "max_rows": 1000},
                "result": f"success - {view_data.get('row_count', 0)} rows"
            }]
        }
    except Exception as e:
        logger.error(f"Error fetching view data: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to fetch view data: {str(e)}",
            "view_data": None,
            "view_metadata": None,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_view_data",
                "args": {"view_id": view_ids[0] if view_ids else None},
                "result": "error",
                "error": str(e)
            }]
        }
