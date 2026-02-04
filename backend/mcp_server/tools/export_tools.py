"""MCP Tools for data export operations."""
import logging
from typing import Optional, Dict, List, Any
import json
import csv
import io

from app.services.agents.summary_agent import SummaryAgent
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
_summary_agent: Optional[SummaryAgent] = None
_tableau_client: Optional[TableauClient] = None


def get_summary_agent() -> SummaryAgent:
    """Get or create Summary agent instance."""
    global _summary_agent
    if _summary_agent is None:
        _summary_agent = SummaryAgent(tableau_client=get_tableau_client())
    return _summary_agent


def get_tableau_client() -> TableauClient:
    """Get or create Tableau client instance."""
    global _tableau_client
    if _tableau_client is None:
        _tableau_client = TableauClient()
    return _tableau_client


@mcp.tool()
async def tableau_export_view_data(
    view_id: str,
    format: str = "json",
) -> Dict[str, Any]:
    """
    Export data from a Tableau view.
    
    Args:
        view_id: View ID to export
        format: Export format (json, csv, excel)
    
    Returns:
        Dictionary with 'data', 'format', 'row_count', and format-specific content
    """
    try:
        agent = get_summary_agent()
        result = await agent.export_views([view_id], format=format)
        
        if result.get("datasets"):
            dataset = result["datasets"][0]
            
            # Format data based on requested format
            formatted_data = None
            if format == "csv":
                formatted_data = _format_as_csv(dataset.get("data", []), dataset.get("columns", []))
            elif format == "json":
                formatted_data = json.dumps(dataset.get("data", []), indent=2)
            else:
                formatted_data = dataset.get("data", [])
            
            return {
                "data": dataset.get("data", []),
                "columns": dataset.get("columns", []),
                "row_count": dataset.get("row_count", 0),
                "format": format,
                "formatted": formatted_data,
            }
        else:
            return {
                "error": "No data exported",
                "data": [],
                "columns": [],
                "row_count": 0,
                "format": format,
            }
    except Exception as e:
        logger.error(f"Error exporting view data: {e}")
        return {
            "error": str(e),
            "data": [],
            "columns": [],
            "row_count": 0,
            "format": format,
        }


@mcp.tool()
async def tableau_export_crosstab(
    view_id: str,
    row_fields: List[str],
    col_fields: List[str],
    measure: str,
) -> Dict[str, Any]:
    """
    Export data as a crosstab (pivot table).
    
    Args:
        view_id: View ID to export
        row_fields: List of field names for rows
        col_fields: List of field names for columns
        measure: Measure field name to aggregate
    
    Returns:
        Dictionary with 'crosstab' structure containing 'rows', 'columns', and 'data'
    """
    try:
        agent = get_summary_agent()
        view_data = await agent._get_view_data(view_id)
        
        data = view_data.get("data", [])
        columns = view_data.get("columns", [])
        
        if not data or not columns:
            return {
                "error": "No data available",
                "crosstab": {
                    "rows": [],
                    "columns": [],
                    "data": {}
                }
            }
        
        # Build crosstab structure
        crosstab = {
            "rows": [],
            "columns": [],
            "data": {}
        }
        
        # Get column indices
        row_indices = [columns.index(f) if f in columns else None for f in row_fields]
        col_indices = [columns.index(f) if f in columns else None for f in col_fields]
        measure_index = columns.index(measure) if measure in columns else None
        
        if measure_index is None:
            return {
                "error": f"Measure '{measure}' not found in columns",
                "crosstab": crosstab
            }
        
        # Build crosstab data
        row_keys = set()
        col_keys = set()
        
        for row in data:
            if len(row) <= max([i for i in row_indices + col_indices + [measure_index] if i is not None]):
                continue
            
            row_key = tuple(row[i] if i is not None else "" for i in row_indices)
            col_key = tuple(row[i] if i is not None else "" for i in col_indices)
            measure_value = row[measure_index] if measure_index is not None else 0
            
            row_keys.add(row_key)
            col_keys.add(col_key)
            
            if row_key not in crosstab["data"]:
                crosstab["data"][row_key] = {}
            crosstab["data"][row_key][col_key] = measure_value
        
        crosstab["rows"] = [list(k) for k in sorted(row_keys)]
        crosstab["columns"] = [list(k) for k in sorted(col_keys)]
        
        return {
            "crosstab": crosstab,
            "row_fields": row_fields,
            "col_fields": col_fields,
            "measure": measure,
        }
    except Exception as e:
        logger.error(f"Error exporting crosstab: {e}")
        return {
            "error": str(e),
            "crosstab": {
                "rows": [],
                "columns": [],
                "data": {}
            }
        }


@mcp.tool()
async def tableau_export_summary(
    view_ids: List[str],
    aggregation_type: str = "sum",
    column: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export aggregated summary across multiple views.
    
    Args:
        view_ids: List of view IDs to summarize
        aggregation_type: Type of aggregation (sum, avg, count, max, min)
        column: Optional column name to aggregate (if None, aggregates all numeric columns)
    
    Returns:
        Dictionary with 'total', 'by_view', and aggregation details
    """
    try:
        agent = get_summary_agent()
        result = await agent.aggregate_across_views(
            view_ids=view_ids,
            aggregation_type=aggregation_type,
            column=column
        )
        
        return result
    except Exception as e:
        logger.error(f"Error exporting summary: {e}")
        return {
            "error": str(e),
            "total": 0,
            "by_view": {},
            "aggregation_type": aggregation_type,
        }


@mcp.tool()
async def tableau_batch_export(
    view_ids: List[str],
    format: str = "json",
) -> Dict[str, Any]:
    """
    Export data from multiple views in batch.
    
    Args:
        view_ids: List of view IDs to export
        format: Export format (json, csv, excel)
    
    Returns:
        Dictionary with 'exports' list, 'total_rows', and 'view_count'
    """
    try:
        agent = get_summary_agent()
        result = await agent.export_views(view_ids, format=format)
        
        exports = []
        for dataset in result.get("datasets", []):
            export_data = {
                "view_id": dataset.get("view_id"),
                "row_count": dataset.get("row_count", 0),
                "column_count": len(dataset.get("columns", [])),
                "format": format,
            }
            
            if format == "json":
                export_data["data"] = dataset.get("data", [])
            elif format == "csv":
                export_data["data"] = _format_as_csv(
                    dataset.get("data", []),
                    dataset.get("columns", [])
                )
            
            exports.append(export_data)
        
        return {
            "exports": exports,
            "total_rows": result.get("total_rows", 0),
            "view_count": len(view_ids),
            "format": format,
        }
    except Exception as e:
        logger.error(f"Error in batch export: {e}")
        return {
            "error": str(e),
            "exports": [],
            "total_rows": 0,
            "view_count": len(view_ids),
            "format": format,
        }


def _format_as_csv(data: List[List[Any]], columns: List[str]) -> str:
    """Format data as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    if columns:
        writer.writerow(columns)
    
    # Write data rows
    for row in data:
        writer.writerow(row)
    
    return output.getvalue()
