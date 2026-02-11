"""MCP Tools for Tableau operations."""
import logging
from typing import Optional, Dict, List, Any
from app.services.tableau.client import TableauClient, TableauClientError

logger = logging.getLogger(__name__)

# Import mcp from package __init__ to avoid circular import
# This ensures we get the same instance that server.py created
try:
    from mcp_server import get_mcp
    mcp = get_mcp()
    if mcp is None:
        logger.error("mcp instance not available - tools will not be registered")
except ImportError:
    # Fallback: try importing from server directly
    try:
        from mcp_server.server import mcp
    except ImportError:
        logger.error("Failed to import mcp - tools will not be registered")
        mcp = None


# Get a singleton Tableau client instance
_tableau_client: Optional[TableauClient] = None


def get_tableau_client() -> TableauClient:
    """Get or create Tableau client instance."""
    global _tableau_client
    if _tableau_client is None:
        _tableau_client = TableauClient()
    return _tableau_client


@mcp.tool()
async def tableau_list_datasources(
    project_id: Optional[str] = None,
    page_size: int = 100,
    page_number: int = 1,
) -> Dict[str, Any]:
    """
    List all datasources from Tableau Server.
    
    Args:
        project_id: Optional project ID to filter by
        page_size: Number of results per page (1-1000, default: 100)
        page_number: Page number (1-indexed, default: 1)
    
    Returns:
        Dictionary with 'datasources' list containing datasource information
    """
    try:
        client = get_tableau_client()
        result = await client.get_datasources(
            project_id=project_id,
            page_size=page_size,
            page_number=page_number,
        )
        datasources = result["items"]
        pagination = result["pagination"]
        
        return {
            "datasources": datasources,
            "count": len(datasources),
            "page_size": page_size,
            "page_number": page_number,
            "total_available": pagination.get("totalAvailable"),
        }
    except TableauClientError as e:
        logger.error(f"Tableau client error: {e}")
        return {
            "error": str(e),
            "datasources": [],
            "count": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected error listing datasources: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "datasources": [],
            "count": 0,
        }


@mcp.tool()
async def tableau_list_views(
    datasource_id: Optional[str] = None,
    workbook_id: Optional[str] = None,
    page_size: int = 100,
    page_number: int = 1,
) -> Dict[str, Any]:
    """
    List all views from Tableau Server.
    
    Args:
        datasource_id: Optional datasource ID to filter by
        workbook_id: Optional workbook ID to filter by
        page_size: Number of results per page (1-1000, default: 100)
        page_number: Page number (1-indexed, default: 1)
    
    Returns:
        Dictionary with 'views' list containing view information
    """
    try:
        client = get_tableau_client()
        views = await client.get_views(
            datasource_id=datasource_id,
            workbook_id=workbook_id,
            page_size=page_size,
            page_number=page_number,
        )
        
        return {
            "views": views,
            "count": len(views),
            "page_size": page_size,
            "page_number": page_number,
        }
    except TableauClientError as e:
        logger.error(f"Tableau client error: {e}")
        return {
            "error": str(e),
            "views": [],
            "count": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected error listing views: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "views": [],
            "count": 0,
        }


@mcp.tool()
async def tableau_query_datasource(
    datasource_id: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Query a datasource with optional filters and column selection.
    
    Args:
        datasource_id: Datasource ID to query (required)
        filters: Optional dictionary of filters (e.g., {"year": "2024", "region": "West"})
        columns: Optional list of column names to return
        limit: Optional limit on number of rows
    
    Returns:
        Dictionary with 'data', 'columns', and 'row_count'
    """
    try:
        client = get_tableau_client()
        result = await client.query_datasource(
            datasource_id=datasource_id,
            filters=filters,
            columns=columns,
            limit=limit,
        )
        
        return result
    except TableauClientError as e:
        logger.error(f"Tableau client error: {e}")
        return {
            "error": str(e),
            "data": [],
            "columns": [],
            "row_count": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected error querying datasource: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "data": [],
            "columns": [],
            "row_count": 0,
        }


@mcp.tool()
async def tableau_get_view_embed_url(
    view_id: str,
    filters: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Get embedding URL for a Tableau view.
    
    Args:
        view_id: View ID (required)
        filters: Optional dictionary of filters (e.g., {"Region": "West"})
        params: Optional URL parameters
    
    Returns:
        Dictionary with 'url' containing the embed URL and 'token'
    """
    try:
        client = get_tableau_client()
        result = await client.get_view_embed_url(
            view_id=view_id,
            filters=filters,
            params=params,
        )
        
        return result
    except TableauClientError as e:
        logger.error(f"Tableau client error: {e}")
        return {
            "error": str(e),
            "url": "",
            "token": "",
        }
    except Exception as e:
        logger.error(f"Unexpected error getting embed URL: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "url": "",
            "token": "",
        }
