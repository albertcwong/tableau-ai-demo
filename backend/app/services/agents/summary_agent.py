"""Summary Agent for multi-view data export and summarization."""
import logging
from typing import Dict, List, Any, Optional
import json

from app.services.ai.client import UnifiedAIClient
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


class SummaryAgent:
    """Agent specialized in exporting and summarizing data from multiple views."""
    
    def __init__(
        self,
        ai_client: Optional[UnifiedAIClient] = None,
        tableau_client: Optional[TableauClient] = None,
        model: str = "gpt-4",
        api_key: Optional[str] = None
    ):
        """Initialize Summary agent.
        
        Args:
            ai_client: Optional AI client instance
            tableau_client: Optional Tableau client instance
            model: AI model to use for summarization
            api_key: Optional API key for AI client
        """
        self.ai_client = ai_client
        self.tableau_client = tableau_client
        self.model = model
        self.api_key = api_key
        self.name = "summary_agent"
    
    async def export_views(
        self,
        view_ids: List[str],
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export data from multiple views.
        
        Args:
            view_ids: List of view IDs to export
            format: Export format (json, csv, excel)
            
        Returns:
            Dictionary with exported datasets and metadata
        """
        if not self.tableau_client:
            from app.services.tableau.client import TableauClient
            self.tableau_client = TableauClient()
        
        datasets = []
        total_rows = 0
        
        for view_id in view_ids:
            try:
                # Get view data using Tableau Data API
                # Note: This would use the actual Tableau Data API endpoint
                # For now, we'll structure the response
                view_data = await self._get_view_data(view_id)
                
                datasets.append({
                    "view_id": view_id,
                    "data": view_data.get("data", []),
                    "columns": view_data.get("columns", []),
                    "row_count": view_data.get("row_count", 0),
                    "format": format
                })
                
                total_rows += view_data.get("row_count", 0)
            except Exception as e:
                logger.error(f"Error exporting view {view_id}: {e}")
                datasets.append({
                    "view_id": view_id,
                    "error": str(e),
                    "data": [],
                    "columns": [],
                    "row_count": 0
                })
        
        return {
            "datasets": datasets,
            "total_rows": total_rows,
            "view_count": len(view_ids),
            "format": format
        }
    
    async def aggregate_across_views(
        self,
        view_ids: List[str],
        aggregation_type: str = "sum",
        column: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate data across multiple views.
        
        Args:
            view_ids: List of view IDs to aggregate
            aggregation_type: Type of aggregation (sum, avg, count, max, min)
            column: Column name to aggregate (if None, aggregates all numeric columns)
            
        Returns:
            Dictionary with aggregated results
        """
        export_result = await self.export_views(view_ids)
        
        by_view = {}
        total = 0
        
        for dataset in export_result["datasets"]:
            view_id = dataset["view_id"]
            if dataset.get("error"):
                continue
            
            data = dataset.get("data", [])
            columns = dataset.get("columns", [])
            
            # Find numeric columns
            if column:
                target_columns = [column] if column in columns else []
            else:
                target_columns = [c for c in columns if self._is_numeric_column(c, data)]
            
            view_total = 0
            for target_col in target_columns:
                col_index = columns.index(target_col) if target_col in columns else None
                if col_index is None:
                    continue
                
                values = [row[col_index] for row in data if len(row) > col_index]
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                
                if aggregation_type.lower() == "sum":
                    col_total = sum(numeric_values)
                elif aggregation_type.lower() == "avg":
                    col_total = sum(numeric_values) / len(numeric_values) if numeric_values else 0
                elif aggregation_type.lower() == "count":
                    col_total = len(numeric_values)
                elif aggregation_type.lower() == "max":
                    col_total = max(numeric_values) if numeric_values else 0
                elif aggregation_type.lower() == "min":
                    col_total = min(numeric_values) if numeric_values else 0
                else:
                    col_total = sum(numeric_values)
                
                view_total += col_total
            
            by_view[view_id] = view_total
            total += view_total
        
        return {
            "total": total,
            "by_view": by_view,
            "aggregation_type": aggregation_type,
            "column": column or "all_numeric"
        }
    
    async def generate_report(
        self,
        view_ids: List[str],
        format: str = "html",
        include_visualizations: bool = True
    ) -> Dict[str, Any]:
        """Generate a summary report from multiple views.
        
        Args:
            view_ids: List of view IDs to include in report
            format: Report format (html, pdf, markdown)
            include_visualizations: Whether to include visualization URLs
            
        Returns:
            Dictionary with report content and metadata
        """
        export_result = await self.export_views(view_ids)
        
        # Generate summary using AI if available
        summary_text = await self._generate_summary_text(export_result)
        
        if format == "html":
            content = self._generate_html_report(export_result, summary_text, include_visualizations)
        elif format == "markdown":
            content = self._generate_markdown_report(export_result, summary_text)
        else:
            content = json.dumps(export_result, indent=2)
        
        visualizations = []
        if include_visualizations:
            for view_id in view_ids:
                try:
                    embed_url = await self._get_view_embed_url(view_id)
                    visualizations.append({
                        "view_id": view_id,
                        "embed_url": embed_url
                    })
                except Exception as e:
                    logger.error(f"Error getting embed URL for view {view_id}: {e}")
        
        return {
            "content": content,
            "format": format,
            "visualizations": visualizations,
            "view_count": len(view_ids),
            "total_rows": export_result["total_rows"]
        }
    
    async def _get_view_data(self, view_id: str) -> Dict[str, Any]:
        """Get data from a view using Tableau Data API."""
        if not self.tableau_client:
            from app.services.tableau.client import TableauClient
            self.tableau_client = TableauClient()
        
        await self.tableau_client._ensure_authenticated()
        site_id = self.tableau_client.site_id or ""
        
        # Use Tableau Data API endpoint
        endpoint = f"sites/{site_id}/views/{view_id}/data"
        
        try:
            response = await self.tableau_client._request("GET", endpoint)
            
            # Parse response based on Tableau Data API format
            # This is a simplified parser; actual format may vary
            data = response.get("data", {}).get("rows", [])
            columns = response.get("data", {}).get("columns", [])
            
            return {
                "data": data,
                "columns": columns,
                "row_count": len(data)
            }
        except Exception as e:
            logger.error(f"Error getting view data for {view_id}: {e}")
            return {
                "data": [],
                "columns": [],
                "row_count": 0,
                "error": str(e)
            }
    
    async def _get_view_embed_url(self, view_id: str) -> str:
        """Get embed URL for a view."""
        if not self.tableau_client:
            from app.services.tableau.client import TableauClient
            self.tableau_client = TableauClient()
        
        result = await self.tableau_client.get_view_embed_url(view_id=view_id)
        return result.get("url", "")
    
    async def _generate_summary_text(self, export_result: Dict[str, Any]) -> str:
        """Generate summary text using AI."""
        if not self.ai_client:
            from app.services.ai.client import UnifiedAIClient
            from app.core.config import settings
            self.ai_client = UnifiedAIClient(
                gateway_url=settings.GATEWAY_BASE_URL,
                api_key=self.api_key
            )
        
        # Prepare summary prompt
        datasets_summary = []
        for dataset in export_result.get("datasets", []):
            datasets_summary.append(
                f"View {dataset['view_id']}: {dataset.get('row_count', 0)} rows, "
                f"{len(dataset.get('columns', []))} columns"
            )
        
        prompt = f"""Summarize the following data export results:

{chr(10).join(datasets_summary)}

Total rows: {export_result.get('total_rows', 0)}
Number of views: {export_result.get('view_count', 0)}

Provide a concise summary highlighting key insights and patterns."""
        
        try:
            response = await self.ai_client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Summary: {export_result.get('view_count', 0)} views exported with {export_result.get('total_rows', 0)} total rows."
    
    def _generate_html_report(
        self,
        export_result: Dict[str, Any],
        summary_text: str,
        include_visualizations: bool
    ) -> str:
        """Generate HTML report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Tableau Data Export Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Tableau Data Export Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>{summary_text}</p>
        <p><strong>Total Rows:</strong> {export_result.get('total_rows', 0)}</p>
        <p><strong>Views Exported:</strong> {export_result.get('view_count', 0)}</p>
    </div>
"""
        
        for dataset in export_result.get("datasets", []):
            html += f"""
    <h2>View {dataset['view_id']}</h2>
    <p>Rows: {dataset.get('row_count', 0)}, Columns: {len(dataset.get('columns', []))}</p>
"""
            if include_visualizations:
                html += f"""    <p><a href="#">View Visualization</a></p>"""
        
        html += """
</body>
</html>"""
        return html
    
    def _generate_markdown_report(
        self,
        export_result: Dict[str, Any],
        summary_text: str
    ) -> str:
        """Generate Markdown report."""
        md = f"""# Tableau Data Export Report

## Summary

{summary_text}

**Total Rows:** {export_result.get('total_rows', 0)}
**Views Exported:** {export_result.get('view_count', 0)}

"""
        
        for dataset in export_result.get("datasets", []):
            md += f"""## View {dataset['view_id']}

- Rows: {dataset.get('row_count', 0)}
- Columns: {len(dataset.get('columns', []))}

"""
        
        return md
    
    def _is_numeric_column(self, column_name: str, data: List[List[Any]]) -> bool:
        """Check if a column contains numeric data."""
        if not data:
            return False
        
        # Find column index
        # This is simplified; assumes first row has column names
        # In practice, you'd have column metadata
        sample_size = min(10, len(data))
        numeric_count = 0
        
        for row in data[:sample_size]:
            if len(row) > 0:
                value = row[0] if isinstance(row, list) else row
                if isinstance(value, (int, float)):
                    numeric_count += 1
        
        return numeric_count / sample_size > 0.5 if sample_size > 0 else False
