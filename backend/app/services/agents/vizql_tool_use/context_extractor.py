"""
Extract structured context from query results for follow-up queries.

This module extracts dimension values from query results so the LLM
can reference them in follow-up queries without parsing natural language.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def extract_dimension_values(
    query_results: Dict[str, Any],
    max_values_per_dimension: int = 50
) -> Dict[str, List[str]]:
    """
    Extract dimension values from query results.
    
    This provides structured context for follow-up queries like:
    - "show me sales for those cities" → knows which cities from previous result
    - "top 3 customers in each of those" → knows which dimension values to filter
    
    Args:
        query_results: Query results with columns and data
        max_values_per_dimension: Max values to extract per dimension (prevent huge lists)
        
    Returns:
        Dict mapping dimension names to lists of values
        Example: {"City": ["Houston", "Philadelphia"], "Region": ["West", "East"]}
    """
    if not query_results or not isinstance(query_results, dict):
        return {}
    
    columns = query_results.get("columns", [])
    data = query_results.get("data", [])
    
    if not columns or not data:
        return {}
    
    # Identify dimension columns (non-aggregated columns)
    # Heuristic: dimensions are string columns or columns without aggregation functions
    dimension_indices = []
    dimension_names = []
    
    for i, col in enumerate(columns):
        col_str = str(col)
        # Skip aggregated columns (SUM, AVG, COUNT, etc.)
        if not any(agg in col_str.upper() for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(', 'COUNTD(']):
            dimension_indices.append(i)
            dimension_names.append(col_str)
    
    if not dimension_indices:
        logger.info("No dimension columns found in query results")
        return {}
    
    # Extract unique values for each dimension
    dimension_values = {}
    
    for idx, name in zip(dimension_indices, dimension_names):
        values = set()
        for row in data:
            if isinstance(row, (list, tuple)) and len(row) > idx:
                value = row[idx]
                if value is not None and value != "":
                    # Convert to string for consistency
                    values.add(str(value))
        
        # Only store if we have values and not too many
        if values and len(values) <= max_values_per_dimension:
            dimension_values[name] = sorted(list(values))
            logger.info(f"Extracted {len(dimension_values[name])} values for dimension '{name}': {dimension_values[name][:5]}...")
        elif len(values) > max_values_per_dimension:
            logger.warning(f"Dimension '{name}' has {len(values)} values (> {max_values_per_dimension}), skipping to avoid context overload")
    
    return dimension_values


def format_context_for_llm(dimension_values: Dict[str, List[str]]) -> str:
    """
    Format extracted dimension values for LLM context.
    
    Returns a clear, structured summary the LLM can easily reference.
    """
    if not dimension_values:
        return ""
    
    parts = []
    for dim_name, values in dimension_values.items():
        if len(values) <= 10:
            # Show all values if small list
            values_str = ", ".join(values)
            parts.append(f"  - {dim_name}: {values_str}")
        else:
            # Show first 10 + count if large list
            values_str = ", ".join(values[:10])
            parts.append(f"  - {dim_name}: {values_str} (and {len(values) - 10} more)")
    
    return "\n[Context from previous query]\n" + "\n".join(parts)
