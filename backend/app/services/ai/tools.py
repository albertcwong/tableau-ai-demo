"""AI tools for function calling with Tableau operations."""
import logging
from typing import Dict, List, Any, Optional, Callable
from app.services.tableau.client import TableauClient, TableauClientError

logger = logging.getLogger(__name__)


# Tool definitions in OpenAI function calling format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_datasources",
            "description": "List all available Tableau datasources. Use this when the user asks to see datasources, list data sources, or browse available data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Optional project ID to filter datasources by project"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_views",
            "description": "List all available Tableau views (dashboards/worksheets). Use this when the user asks to see views, dashboards, or visualizations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datasource_id": {
                        "type": "string",
                        "description": "Optional datasource ID to filter views by datasource"
                    },
                    "workbook_id": {
                        "type": "string",
                        "description": "Optional workbook ID to filter views by workbook"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_datasource",
            "description": "Query a Tableau datasource with filters. Use this when the user asks to query data, filter data, get specific records, or analyze data from a datasource.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datasource_id": {
                        "type": "string",
                        "description": "The ID of the datasource to query"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Dictionary of filters to apply (e.g., {'year': '2024', 'region': 'West'})",
                        "additionalProperties": {
                            "type": "string"
                        }
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of column names to return. If not specified, all columns are returned."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional limit on number of rows to return"
                    }
                },
                "required": ["datasource_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "embed_view",
            "description": "Get the embedding URL and token for a Tableau view. Use this when the user asks to show a view, display a dashboard, or embed a visualization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "view_id": {
                        "type": "string",
                        "description": "The ID of the view to embed"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional dictionary of filters to apply to the view (e.g., {'Region': 'West'})",
                        "additionalProperties": {
                            "type": "string"
                        }
                    }
                },
                "required": ["view_id"]
            }
        }
    }
]


def get_tools() -> List[Dict[str, Any]]:
    """Get list of available tools for function calling."""
    return TOOLS


async def list_datasources_tool(
    project_id: Optional[str] = None,
    tableau_client: Optional[TableauClient] = None
) -> List[Dict[str, Any]]:
    """
    Tool function: List all datasources.
    
    Args:
        project_id: Optional project ID to filter by
        tableau_client: Optional Tableau client instance (creates new if not provided)
        
    Returns:
        List of datasource dictionaries
    """
    client = tableau_client or TableauClient()
    try:
        datasources = await client.get_datasources(project_id=project_id)
        result = []
        for ds in datasources:
            project = ds.get("project", {})
            result.append({
                "id": ds.get("id", ""),
                "name": ds.get("name", ""),
                "project_id": project.get("id") if isinstance(project, dict) else None,
                "project_name": project.get("name") if isinstance(project, dict) else None,
                "content_url": ds.get("contentUrl"),
            })
        return result
    except Exception as e:
        logger.error(f"Error in list_datasources_tool: {e}", exc_info=True)
        raise
    finally:
        if not tableau_client:  # Only close if we created it
            await client.close()


async def list_views_tool(
    datasource_id: Optional[str] = None,
    workbook_id: Optional[str] = None,
    tableau_client: Optional[TableauClient] = None
) -> List[Dict[str, Any]]:
    """
    Tool function: List all views.
    
    Args:
        datasource_id: Optional datasource ID to filter by
        workbook_id: Optional workbook ID to filter by
        tableau_client: Optional Tableau client instance (creates new if not provided)
        
    Returns:
        List of view dictionaries
    """
    client = tableau_client or TableauClient()
    try:
        views = await client.get_views(
            datasource_id=datasource_id,
            workbook_id=workbook_id
        )
        result = []
        for view in views:
            workbook = view.get("workbook", {})
            datasource = view.get("datasource", {})
            result.append({
                "id": view.get("id", ""),
                "name": view.get("name", ""),
                "workbook_id": workbook.get("id") if isinstance(workbook, dict) else None,
                "workbook_name": workbook.get("name") if isinstance(workbook, dict) else None,
                "datasource_id": datasource.get("id") if isinstance(datasource, dict) else None,
                "content_url": view.get("contentUrl"),
            })
        return result
    except Exception as e:
        logger.error(f"Error in list_views_tool: {e}", exc_info=True)
        raise
    finally:
        if not tableau_client:  # Only close if we created it
            await client.close()


async def query_datasource_tool(
    datasource_id: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: Optional[int] = None,
    tableau_client: Optional[TableauClient] = None
) -> Dict[str, Any]:
    """
    Tool function: Query a datasource.
    
    Args:
        datasource_id: Datasource ID to query
        filters: Optional dictionary of filters
        columns: Optional list of column names to return
        limit: Optional row limit
        tableau_client: Optional Tableau client instance (creates new if not provided)
        
    Returns:
        Dictionary with data, columns, and row_count
    """
    client = tableau_client or TableauClient()
    try:
        result = await client.query_datasource(
            datasource_id=datasource_id,
            filters=filters,
            columns=columns,
            limit=limit
        )
        return {
            "data": result["data"],
            "columns": result["columns"],
            "row_count": result["row_count"],
            "datasource_id": datasource_id
        }
    except Exception as e:
        logger.error(f"Error in query_datasource_tool: {e}", exc_info=True)
        raise
    finally:
        if not tableau_client:  # Only close if we created it
            await client.close()


async def embed_view_tool(
    view_id: str,
    filters: Optional[Dict[str, str]] = None,
    tableau_client: Optional[TableauClient] = None
) -> Dict[str, Any]:
    """
    Tool function: Get embed URL for a view.
    
    Args:
        view_id: View ID to embed
        filters: Optional dictionary of filters
        tableau_client: Optional Tableau client instance (creates new if not provided)
        
    Returns:
        Dictionary with url, token, view_id, and workbook_id
    """
    client = tableau_client or TableauClient()
    try:
        result = await client.get_view_embed_url(
            view_id=view_id,
            filters=filters
        )
        return {
            "url": result["url"],
            "token": result.get("token"),
            "view_id": result["view_id"],
            "workbook_id": result.get("workbook_id")
        }
    except Exception as e:
        logger.error(f"Error in embed_view_tool: {e}", exc_info=True)
        raise
    finally:
        if not tableau_client:  # Only close if we created it
            await client.close()


# Tool registry mapping function names to implementations
TOOL_REGISTRY: Dict[str, Callable] = {
    "list_datasources": list_datasources_tool,
    "list_views": list_views_tool,
    "query_datasource": query_datasource_tool,
    "embed_view": embed_view_tool,
}


async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tableau_client: Optional[TableauClient] = None
) -> Dict[str, Any]:
    """
    Execute a tool by name with given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool
        tableau_client: Optional Tableau client instance (reused across tool calls)
        
    Returns:
        Dictionary with status and result data
        
    Raises:
        ValueError: If tool_name is not found
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "status": "error",
            "message": f"Unknown tool: {tool_name}",
            "available_tools": list(TOOL_REGISTRY.keys())
        }
    
    try:
        tool_func = TOOL_REGISTRY[tool_name]
        result = await tool_func(tableau_client=tableau_client, **arguments)
        
        return {
            "status": "success",
            "data": result,
            "tool": tool_name
        }
    except TableauClientError as e:
        logger.error(f"Tableau client error executing {tool_name}: {e}")
        return {
            "status": "error",
            "message": f"Tableau error: {str(e)}",
            "tool": tool_name
        }
    except Exception as e:
        logger.error(f"Error executing {tool_name}: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error executing tool: {str(e)}",
            "tool": tool_name
        }


def format_tool_result(tool_result: Dict[str, Any]) -> str:
    """
    Format tool result for display in chat.
    
    Args:
        tool_result: Result dictionary from execute_tool
        
    Returns:
        Formatted string representation
    """
    if tool_result["status"] == "error":
        return f"Error: {tool_result.get('message', 'Unknown error')}"
    
    tool_name = tool_result.get("tool", "unknown")
    data = tool_result.get("data", {})
    
    if tool_name == "list_datasources":
        datasources = data if isinstance(data, list) else []
        if not datasources:
            return "No datasources found."
        lines = [f"Found {len(datasources)} datasource(s):"]
        for ds in datasources:
            project = f" (Project: {ds.get('project_name', 'N/A')})" if ds.get('project_name') else ""
            lines.append(f"- {ds.get('name', 'Unknown')} (ID: {ds.get('id', 'N/A')}){project}")
        return "\n".join(lines)
    
    elif tool_name == "list_views":
        views = data if isinstance(data, list) else []
        if not views:
            return "No views found."
        lines = [f"Found {len(views)} view(s):"]
        for view in views:
            workbook = f" (Workbook: {view.get('workbook_name', 'N/A')})" if view.get('workbook_name') else ""
            lines.append(f"- {view.get('name', 'Unknown')} (ID: {view.get('id', 'N/A')}){workbook}")
        return "\n".join(lines)
    
    elif tool_name == "query_datasource":
        columns = data.get("columns", [])
        rows = data.get("data", [])
        row_count = data.get("row_count", len(rows))
        
        if not rows:
            return f"Query returned no results for datasource {data.get('datasource_id', 'N/A')}."
        
        lines = [f"Query results ({row_count} row(s)):"]
        lines.append(f"Columns: {', '.join(columns)}")
        lines.append("\nData:")
        
        # Show first 10 rows
        for i, row in enumerate(rows[:10], 1):
            row_str = ", ".join(str(val) for val in row)
            lines.append(f"  Row {i}: {row_str}")
        
        if len(rows) > 10:
            lines.append(f"\n... and {len(rows) - 10} more row(s)")
        
        return "\n".join(lines)
    
    elif tool_name == "embed_view":
        return (
            f"View embedding URL:\n"
            f"URL: {data.get('url', 'N/A')}\n"
            f"View ID: {data.get('view_id', 'N/A')}\n"
            f"Workbook ID: {data.get('workbook_id', 'N/A')}\n"
            f"Token: {data.get('token', 'N/A')[:20]}..." if data.get('token') else "Token: N/A"
        )
    
    else:
        # Generic formatting
        import json
        return json.dumps(data, indent=2)
