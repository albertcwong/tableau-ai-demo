"""VizQL Data Service Agent for query construction and execution."""
import logging
from typing import Dict, List, Any, Optional
import re

from app.services.ai.client import UnifiedAIClient
from app.services.tableau.client import TableauClient

logger = logging.getLogger(__name__)


class VDSAgent:
    """Agent specialized in VizQL query construction and execution."""
    
    def __init__(
        self,
        ai_client: Optional[UnifiedAIClient] = None,
        tableau_client: Optional[TableauClient] = None,
        model: str = "gpt-4",
        api_key: Optional[str] = None
    ):
        """Initialize VizQL agent.
        
        Args:
            ai_client: Optional AI client instance
            tableau_client: Optional Tableau client instance
            model: AI model to use for query construction
            api_key: Optional API key for AI client
        """
        self.ai_client = ai_client
        self.tableau_client = tableau_client
        self.model = model
        self.api_key = api_key
        self.name = "vds_agent"
    
    async def analyze_datasource(self, datasource_id: str) -> Dict[str, Any]:
        """Analyze datasource schema and structure.
        
        Args:
            datasource_id: Datasource ID to analyze
            
        Returns:
            Dictionary with schema information including columns, measures, dimensions
        """
        if not self.tableau_client:
            from app.services.tableau.client import TableauClient
            self.tableau_client = TableauClient()
        
        try:
            # Get datasource details
            await self.tableau_client._ensure_authenticated()
            site_id = self.tableau_client.site_id or ""
            
            endpoint = f"sites/{site_id}/datasources/{datasource_id}"
            datasource_info = await self.tableau_client._request("GET", endpoint)
            
            # Extract schema information
            schema = {
                "datasource_id": datasource_id,
                "name": datasource_info.get("datasource", {}).get("name", ""),
                "columns": [],
                "measures": [],
                "dimensions": [],
                "calculated_fields": [],
            }
            
            # Try to get column information from datasource metadata
            # Note: This may require GraphQL Metadata API or additional endpoints
            # For now, we'll structure it for future enhancement
            fields = datasource_info.get("datasource", {}).get("fields", {}).get("field", [])
            if not isinstance(fields, list):
                fields = [fields] if fields else []
            
            for field in fields:
                field_name = field.get("name", "")
                field_type = field.get("dataType", "").lower()
                role = field.get("role", "").lower()
                
                if role == "measure" or field_type in ["int", "float", "double", "real"]:
                    schema["measures"].append({
                        "name": field_name,
                        "type": field_type,
                        "aggregation": field.get("defaultAggregation", "sum")
                    })
                else:
                    schema["dimensions"].append({
                        "name": field_name,
                        "type": field_type
                    })
                
                schema["columns"].append({
                    "name": field_name,
                    "type": field_type,
                    "role": role
                })
            
            return schema
        except Exception as e:
            logger.error(f"Error analyzing datasource {datasource_id}: {e}")
            return {
                "datasource_id": datasource_id,
                "error": str(e),
                "columns": [],
                "measures": [],
                "dimensions": [],
                "calculated_fields": [],
            }
    
    def construct_query(
        self,
        user_query: str,
        datasource_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construct VizQL query from natural language.
        
        Args:
            user_query: Natural language query
            datasource_context: Datasource schema and context
            
        Returns:
            Dictionary with vizql query, explanation, and validation status
        """
        # Extract intent from query
        measures = self._extract_measures(user_query, datasource_context)
        dimensions = self._extract_dimensions(user_query, datasource_context)
        filters = self._extract_filters(user_query)
        aggregations = self._extract_aggregations(user_query)
        
        # Build VizQL-like query structure
        # Note: Actual VizQL syntax is complex; this is a simplified representation
        vizql_parts = []
        
        # SELECT clause
        select_parts = []
        for measure in measures:
            agg = aggregations.get(measure, "SUM")
            select_parts.append(f"{agg}([{measure}]) AS {measure.lower()}_total")
        
        if select_parts:
            vizql_parts.append(f"SELECT {', '.join(select_parts)}")
        else:
            vizql_parts.append("SELECT *")
        
        # FROM clause
        datasource_id = datasource_context.get("id", datasource_context.get("datasource_id", "datasource"))
        vizql_parts.append(f"FROM [{datasource_id}]")
        
        # WHERE clause (filters)
        if filters:
            filter_parts = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_parts.append(f"[{key}] = '{value}'")
                else:
                    filter_parts.append(f"[{key}] = {value}")
            vizql_parts.append(f"WHERE {' AND '.join(filter_parts)}")
        
        # GROUP BY clause
        if dimensions:
            dim_names = [f"[{d}]" for d in dimensions]
            vizql_parts.append(f"GROUP BY {', '.join(dim_names)}")
        
        vizql_query = "\n".join(vizql_parts)
        
        explanation = f"Query extracts {', '.join(measures) if measures else 'all fields'} "
        if dimensions:
            explanation += f"grouped by {', '.join(dimensions)} "
        if filters:
            explanation += f"filtered by {', '.join(filters.keys())}"
        
        return {
            "vizql": vizql_query,
            "explanation": explanation,
            "valid": True,
            "measures": measures,
            "dimensions": dimensions,
            "filters": filters,
        }
    
    def validate_query(self, vizql_query: str) -> bool:
        """Validate VizQL query syntax.
        
        Args:
            vizql_query: VizQL query string to validate
            
        Returns:
            True if query appears valid, False otherwise
        """
        if not vizql_query or not vizql_query.strip():
            return False
        
        # Basic syntax checks
        query_upper = vizql_query.upper()
        
        # Must have SELECT
        if "SELECT" not in query_upper:
            return False
        
        # Check for balanced brackets
        open_brackets = vizql_query.count("[")
        close_brackets = vizql_query.count("]")
        if open_brackets != close_brackets:
            return False
        
        # Check for common SQL-like structure
        # This is a simplified validator; real VizQL has more complex syntax
        return True
    
    def optimize_query(self, vizql_query: str, datasource_context: Dict[str, Any]) -> str:
        """Apply optimization heuristics to VizQL query.
        
        Args:
            vizql_query: Original VizQL query
            datasource_context: Datasource context for optimization hints
            
        Returns:
            Optimized VizQL query
        """
        optimized = vizql_query
        
        # Add LIMIT if query doesn't have one and datasource is large
        if "LIMIT" not in optimized.upper() and datasource_context.get("row_count", 0) > 10000:
            optimized += "\nLIMIT 10000"
        
        # Suggest index usage hints (if applicable)
        # This would require more datasource metadata
        
        return optimized
    
    def _extract_measures(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Extract measure fields from query."""
        measures = []
        available_measures = [m.get("name", m) if isinstance(m, dict) else m 
                             for m in context.get("measures", [])]
        
        query_lower = query.lower()
        for measure in available_measures:
            measure_name = measure if isinstance(measure, str) else measure.get("name", "")
            if measure_name.lower() in query_lower:
                measures.append(measure_name)
        
        # Common measure keywords
        measure_keywords = ["sales", "revenue", "profit", "cost", "amount", "total", "sum", "count"]
        for keyword in measure_keywords:
            if keyword in query_lower and keyword not in [m.lower() for m in measures]:
                # Try to find matching measure
                for m in available_measures:
                    if keyword in m.lower():
                        measures.append(m)
                        break
        
        return measures
    
    def _extract_dimensions(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Extract dimension fields from query."""
        dimensions = []
        available_dims = [d.get("name", d) if isinstance(d, dict) else d 
                         for d in context.get("dimensions", [])]
        
        query_lower = query.lower()
        for dim in available_dims:
            dim_name = dim if isinstance(dim, str) else dim.get("name", "")
            if dim_name.lower() in query_lower:
                dimensions.append(dim_name)
        
        # Common dimension keywords
        dim_keywords = ["by", "group by", "region", "year", "month", "category", "product"]
        for keyword in dim_keywords:
            if keyword in query_lower:
                # Extract dimension after "by"
                if "by" in query_lower:
                    after_by = query_lower.split("by", 1)[1].strip()
                    words = after_by.split()[:3]  # Take first few words
                    for word in words:
                        for d in available_dims:
                            if word in d.lower():
                                dimensions.append(d)
                                break
        
        return dimensions
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract filter conditions from query."""
        filters = {}
        
        # Year filter
        year_match = re.search(r'(?:year|yr|in)\s+(\d{4})', query, re.IGNORECASE)
        if year_match:
            filters["year"] = year_match.group(1)
        
        # Region filter
        region_match = re.search(r'region[:\s=]+([A-Za-z\s]+)', query, re.IGNORECASE)
        if region_match:
            filters["region"] = region_match.group(1).strip()
        
        # Date range
        date_match = re.search(r'(\d{4})-(\d{4})', query)
        if date_match:
            filters["start_year"] = date_match.group(1)
            filters["end_year"] = date_match.group(2)
        
        return filters
    
    def _extract_aggregations(self, query: str) -> Dict[str, str]:
        """Extract aggregation functions from query."""
        aggregations = {}
        query_lower = query.lower()
        
        # Look for aggregation keywords
        if "average" in query_lower or "avg" in query_lower:
            aggregations["default"] = "AVG"
        elif "count" in query_lower:
            aggregations["default"] = "COUNT"
        elif "max" in query_lower or "maximum" in query_lower:
            aggregations["default"] = "MAX"
        elif "min" in query_lower or "minimum" in query_lower:
            aggregations["default"] = "MIN"
        else:
            aggregations["default"] = "SUM"
        
        return aggregations
