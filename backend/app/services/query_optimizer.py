"""Query optimization utilities."""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def simplify_query_for_large_dataset(query: Dict[str, Any], estimated_rows: Optional[int] = None) -> Dict[str, Any]:
    """
    Simplify query for large datasets.
    
    Args:
        query: Original VizQL query
        estimated_rows: Estimated number of rows (if known)
    
    Returns:
        Simplified query with limits and optimizations
    """
    simplified = query.copy()
    
    # Add limit if not present and dataset is large
    if estimated_rows and estimated_rows > 10000:
        if "options" not in simplified:
            simplified["options"] = {}
        
        # Set reasonable limit
        simplified["options"]["limit"] = 10000
        logger.info(f"Added limit of 10000 to query (estimated {estimated_rows} rows)")
    
    # Ensure returnFormat is OBJECTS for better performance
    if "options" not in simplified:
        simplified["options"] = {}
    
    if "returnFormat" not in simplified["options"]:
        simplified["options"]["returnFormat"] = "OBJECTS"
    
    # Disable disaggregation for large datasets
    if simplified["options"].get("disaggregate", False) and estimated_rows and estimated_rows > 5000:
        simplified["options"]["disaggregate"] = False
        logger.info("Disabled disaggregation for large dataset")
    
    return simplified


def estimate_query_complexity(query: Dict[str, Any]) -> str:
    """
    Estimate query complexity.
    
    Returns:
        "low", "medium", or "high"
    """
    complexity_score = 0
    
    # Count fields
    fields = query.get("query", {}).get("fields", [])
    complexity_score += len(fields)
    
    # Count filters
    filters = query.get("query", {}).get("filters", [])
    complexity_score += len(filters) * 2
    
    # Check for aggregations
    has_aggregations = any(field.get("function") for field in fields)
    if has_aggregations:
        complexity_score += 3
    
    if complexity_score <= 3:
        return "low"
    elif complexity_score <= 8:
        return "medium"
    else:
        return "high"
