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
                "view_metadata": None,
                "views_data": {},
                "views_metadata": {}
            }
        
        logger.info(f"Fetching data for {len(view_ids)} view(s): {view_ids}")
        
        # Fetch data and metadata for all views in parallel
        tasks = []
        for view_id in view_ids:
            tasks.append(_fetch_view_data_cached(view_id, max_rows=1000))
            tasks.append(_fetch_view_metadata_cached(view_id))
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results by view
        views_data = {}
        views_metadata = {}
        total_rows = 0
        successful_fetches = 0
        
        for i, view_id in enumerate(view_ids):
            data_idx = i * 2
            metadata_idx = i * 2 + 1
            
            view_data = results[data_idx]
            view_metadata = results[metadata_idx]
            
            # Handle exceptions
            if isinstance(view_data, Exception):
                logger.error(f"Failed to fetch view data for {view_id}: {view_data}")
                views_data[view_id] = None
            else:
                views_data[view_id] = view_data
                total_rows += view_data.get('row_count', 0)
                successful_fetches += 1
            
            if isinstance(view_metadata, Exception):
                logger.warning(f"Failed to fetch view metadata for {view_id}: {view_metadata}")
                views_metadata[view_id] = {"id": view_id, "name": view_id}
            else:
                views_metadata[view_id] = view_metadata
        
        # For backward compatibility, set first view's data as primary
        first_view_id = view_ids[0]
        primary_view_data = views_data.get(first_view_id)
        primary_view_metadata = views_metadata.get(first_view_id, {})
        
        # Build tool calls for all views
        tool_calls = state.get("tool_calls", [])
        for view_id in view_ids:
            view_data = views_data.get(view_id)
            if view_data:
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "max_rows": 1000},
                    "result": f"success - {view_data.get('row_count', 0)} rows"
                })
            else:
                tool_calls.append({
                    "tool": "get_view_data",
                    "args": {"view_id": view_id, "max_rows": 1000},
                    "result": "error",
                    "error": "Failed to fetch data"
                })
        
        view_count_text = f"{len(view_ids)} view{'s' if len(view_ids) > 1 else ''}"
        thought = f"Fetched data from {successful_fetches}/{len(view_ids)} view(s), total {total_rows} rows"
        
        return {
            **state,
            "view_data": primary_view_data,  # Backward compatibility
            "view_metadata": primary_view_metadata,  # Backward compatibility
            "views_data": views_data,  # All views data
            "views_metadata": views_metadata,  # All views metadata
            "current_thought": thought,
            "tool_calls": tool_calls
        }
    except Exception as e:
        logger.error(f"Error fetching view data: {e}", exc_info=True)
        view_ids = state.get("context_views", [])
        tool_calls = state.get("tool_calls", [])
        for view_id in view_ids:
            tool_calls.append({
                "tool": "get_view_data",
                "args": {"view_id": view_id, "max_rows": 1000},
                "result": "error",
                "error": str(e)
            })
        return {
            **state,
            "error": f"Failed to fetch view data: {str(e)}",
            "view_data": None,
            "view_metadata": None,
            "views_data": {},
            "views_metadata": {},
            "tool_calls": tool_calls
        }
