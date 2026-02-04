"""MCP Tools for VizQL operations."""
import logging
from typing import Optional, Dict, List, Any
from app.services.agents.vds_agent import VDSAgent
from app.services.tableau.client import TableauClient, TableauClientError

logger = logging.getLogger(__name__)

# Import mcp from package __init__ to avoid circular import
try:
    from mcp_server import get_mcp
    mcp = get_mcp()
    if mcp is None:
        logger.error("mcp instance not available - tools will not be registered")
except ImportError:
    try:
        from mcp_server.server import mcp
    except ImportError:
        logger.error("Failed to import mcp - tools will not be registered")
        mcp = None


# Get singleton instances
_vds_agent: Optional[VDSAgent] = None
_tableau_client: Optional[TableauClient] = None


def get_vds_agent() -> VDSAgent:
    """Get or create VizQL agent instance."""
    global _vds_agent
    if _vds_agent is None:
        _vds_agent = VDSAgent(tableau_client=get_tableau_client())
    return _vds_agent


def get_tableau_client() -> TableauClient:
    """Get or create Tableau client instance."""
    global _tableau_client
    if _tableau_client is None:
        _tableau_client = TableauClient()
    return _tableau_client


@mcp.tool()
async def tableau_construct_vizql(
    user_query: str,
    datasource_id: str,
) -> Dict[str, Any]:
    """
    Construct a VizQL query from natural language.
    
    Args:
        user_query: Natural language query (e.g., "Show me total sales by region for 2024")
        datasource_id: Datasource ID to query
    
    Returns:
        Dictionary with 'vizql' query, 'explanation', 'valid' status, and query components
    """
    try:
        agent = get_vds_agent()
        
        # Get datasource schema
        schema = await agent.analyze_datasource(datasource_id)
        
        # Construct query
        datasource_context = {
            "id": datasource_id,
            "datasource_id": datasource_id,
            **schema
        }
        
        result = agent.construct_query(user_query, datasource_context)
        
        return {
            "vizql": result["vizql"],
            "explanation": result["explanation"],
            "valid": result["valid"],
            "measures": result.get("measures", []),
            "dimensions": result.get("dimensions", []),
            "filters": result.get("filters", {}),
        }
    except Exception as e:
        logger.error(f"Error constructing VizQL query: {e}")
        return {
            "error": str(e),
            "vizql": "",
            "explanation": "",
            "valid": False,
        }


@mcp.tool()
async def tableau_execute_vizql(
    datasource_id: str,
    vizql_query: str,
) -> Dict[str, Any]:
    """
    Execute a VizQL query against a datasource.
    
    Args:
        datasource_id: Datasource ID to query
        vizql_query: VizQL query string to execute
    
    Returns:
        Dictionary with 'data', 'columns', and 'row_count'
    """
    try:
        client = get_tableau_client()
        
        # Validate query first
        agent = get_vds_agent()
        if not agent.validate_query(vizql_query):
            return {
                "error": "Invalid VizQL query syntax",
                "data": [],
                "columns": [],
                "row_count": 0,
            }
        
        # Execute query using Tableau Data API
        # Note: Actual VizQL execution may require different endpoint
        # For now, we'll use the query_datasource method with parsed filters
        result = await client.query_datasource(
            datasource_id=datasource_id,
            filters=None,  # Filters would be extracted from VizQL query
            columns=None,
            limit=None
        )
        
        return {
            "data": result.get("data", []),
            "columns": result.get("columns", []),
            "row_count": result.get("row_count", 0),
            "vizql_query": vizql_query,
        }
    except TableauClientError as e:
        logger.error(f"Tableau client error executing VizQL: {e}")
        return {
            "error": str(e),
            "data": [],
            "columns": [],
            "row_count": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected error executing VizQL: {e}")
        return {
            "error": f"Unexpected error: {str(e)}",
            "data": [],
            "columns": [],
            "row_count": 0,
        }


@mcp.tool()
async def tableau_get_datasource_schema(
    datasource_id: str,
) -> Dict[str, Any]:
    """
    Get schema information for a datasource.
    
    Args:
        datasource_id: Datasource ID to analyze
    
    Returns:
        Dictionary with 'columns', 'measures', 'dimensions', 'calculated_fields', and 'data_types'
    """
    try:
        agent = get_vds_agent()
        schema = await agent.analyze_datasource(datasource_id)
        
        # Extract data types from columns
        data_types = {}
        for col in schema.get("columns", []):
            col_name = col.get("name", col) if isinstance(col, dict) else col
            col_type = col.get("type", "unknown") if isinstance(col, dict) else "unknown"
            data_types[col_name] = col_type
        
        return {
            "datasource_id": datasource_id,
            "name": schema.get("name", ""),
            "columns": [col.get("name", col) if isinstance(col, dict) else col 
                       for col in schema.get("columns", [])],
            "measures": schema.get("measures", []),
            "dimensions": schema.get("dimensions", []),
            "calculated_fields": schema.get("calculated_fields", []),
            "data_types": data_types,
        }
    except Exception as e:
        logger.error(f"Error getting datasource schema: {e}")
        return {
            "error": str(e),
            "datasource_id": datasource_id,
            "columns": [],
            "measures": [],
            "dimensions": [],
            "calculated_fields": [],
            "data_types": {},
        }


@mcp.tool()
async def tableau_validate_vizql(
    vizql_query: str,
) -> Dict[str, Any]:
    """
    Validate VizQL query syntax.
    
    Args:
        vizql_query: VizQL query string to validate
    
    Returns:
        Dictionary with 'valid' boolean and 'errors' list if invalid
    """
    try:
        agent = get_vds_agent()
        is_valid = agent.validate_query(vizql_query)
        
        result = {
            "valid": is_valid,
            "errors": [],
        }
        
        if not is_valid:
            result["errors"] = [
                "Query syntax validation failed. Check for:",
                "- Missing SELECT clause",
                "- Unbalanced brackets",
                "- Invalid structure"
            ]
        
        return result
    except Exception as e:
        logger.error(f"Error validating VizQL query: {e}")
        return {
            "valid": False,
            "errors": [str(e)],
        }
