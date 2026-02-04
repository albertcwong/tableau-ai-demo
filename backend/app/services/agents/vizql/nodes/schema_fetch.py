"""Schema fetch node for retrieving datasource schema."""
import logging
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.tableau.client import TableauClient
from app.services.cache import cached
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@cached("schema", ttl_seconds=600)  # Cache schemas for 10 minutes
async def _fetch_schema_cached(datasource_id: str) -> Dict[str, Any]:
    """Cached schema fetch function."""
    tableau_client = TableauClient()
    return await tableau_client.get_datasource_schema(datasource_id)


@track_node_execution("vizql", "schema_fetch")
async def fetch_schema_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Fetch datasource schema using Tableau API.
    
    This is an "Act" step in ReAct.
    Uses caching to avoid repeated API calls.
    """
    try:
        datasource_ids = state.get("context_datasources", [])
        
        if not datasource_ids:
            logger.warning("No datasource in context for schema fetch")
            return {
                **state,
                "error": "No datasource in context. Please add a datasource first.",
                "schema": None
            }
        
        # Use first datasource
        datasource_id = datasource_ids[0]
        
        logger.info(f"Fetching schema for datasource: {datasource_id}")
        
        # Fetch schema (with caching)
        schema_response = await _fetch_schema_cached(datasource_id)
        
        return {
            **state,
            "schema": schema_response,
            "current_thought": f"Fetched schema with {len(schema_response.get('columns', []))} columns",
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_datasource_schema",
                "args": {"datasource_id": datasource_id},
                "result": "success",
                "column_count": len(schema_response.get("columns", []))
            }]
        }
    except Exception as e:
        logger.error(f"Error fetching schema: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to fetch schema: {str(e)}",
            "schema": None,
            "tool_calls": state.get("tool_calls", []) + [{
                "tool": "get_datasource_schema",
                "args": {"datasource_id": datasource_ids[0] if datasource_ids else None},
                "result": "error",
                "error": str(e)
            }]
        }
