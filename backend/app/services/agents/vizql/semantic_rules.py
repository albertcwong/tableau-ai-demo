"""VizQL Semantic Rules Engine.

This module provides semantic understanding of VizQL Data Service queries,
including field roles, aggregation functions, and query patterns.

Extracted from VizQLDataServiceOpenAPISchema.json and VizQL domain knowledge.
"""
from typing import Dict, List, Optional

# VizQL Data Types (from OpenAPI spec)
VIZQL_DATA_TYPES = [
    "INTEGER",
    "REAL",
    "STRING",
    "DATETIME",
    "BOOLEAN",
    "DATE",
    "SPATIAL",
    "UNKNOWN"
]

# VizQL Field Roles
VIZQL_FIELD_ROLES = {
    "MEASURE": {
        "description": "Numeric field requiring aggregation",
        "requires_aggregation": True,
        "compatible_types": ["INTEGER", "REAL"],
        "typical_use": "Calculations, metrics, KPIs"
    },
    "DIMENSION": {
        "description": "Categorical field for grouping",
        "requires_aggregation": False,
        "compatible_types": ["STRING", "DATE", "BOOLEAN", "INTEGER"],
        "typical_use": "Grouping, filtering, categorization"
    },
    "UNKNOWN": {
        "description": "Unknown field role",
        "requires_aggregation": False,
        "compatible_types": VIZQL_DATA_TYPES,
        "typical_use": "Fallback when role is not specified"
    }
}

# VizQL Aggregation Functions (from OpenAPI spec Function enum)
VIZQL_AGGREGATIONS = {
    "SUM": {
        "types": ["INTEGER", "REAL"],
        "description": "Sum numeric values",
        "use_cases": ["sales", "revenue", "amount", "quantity", "total", "profit", "cost"],
        "typical_fields": ["Sales", "Revenue", "Amount", "Quantity", "Profit", "Cost"]
    },
    "AVG": {
        "types": ["INTEGER", "REAL"],
        "description": "Average numeric values",
        "use_cases": ["price", "rating", "score", "duration", "average", "mean"],
        "typical_fields": ["Price", "Rating", "Score", "Duration", "Average"]
    },
    "MEDIAN": {
        "types": ["INTEGER", "REAL"],
        "description": "Median value",
        "use_cases": ["median", "middle", "50th percentile"],
        "typical_fields": ["Median"]
    },
    "COUNT": {
        "types": ["*"],  # Works with any type
        "description": "Count rows",
        "use_cases": ["rows", "records", "entries", "count", "number of"],
        "typical_fields": ["Order ID", "Record ID", "Count"]
    },
    "COUNTD": {
        "types": ["*"],  # Works with any type
        "description": "Count distinct values",
        "use_cases": ["unique", "distinct", "id", "unique count"],
        "typical_fields": ["Customer ID", "Product ID", "Order ID"]
    },
    "MIN": {
        "types": ["INTEGER", "REAL", "DATE", "DATETIME"],
        "description": "Minimum value",
        "use_cases": ["minimum", "earliest", "lowest", "first"],
        "typical_fields": ["Date", "Price", "Value"]
    },
    "MAX": {
        "types": ["INTEGER", "REAL", "DATE", "DATETIME"],
        "description": "Maximum value",
        "use_cases": ["maximum", "latest", "highest", "last"],
        "typical_fields": ["Date", "Price", "Value"]
    },
    "STDEV": {
        "types": ["INTEGER", "REAL"],
        "description": "Standard deviation",
        "use_cases": ["standard deviation", "stdev", "variability"],
        "typical_fields": ["Value", "Score"]
    },
    "VAR": {
        "types": ["INTEGER", "REAL"],
        "description": "Variance",
        "use_cases": ["variance", "var", "variability"],
        "typical_fields": ["Value", "Score"]
    },
    "COLLECT": {
        "types": ["*"],
        "description": "Collect values into a set",
        "use_cases": ["collect", "set", "gather"],
        "typical_fields": []
    },
    # Date/time aggregations
    "YEAR": {
        "types": ["DATE", "DATETIME"],
        "description": "Extract year from date",
        "use_cases": ["year", "by year"],
        "typical_fields": ["Date", "Order Date", "Ship Date"]
    },
    "QUARTER": {
        "types": ["DATE", "DATETIME"],
        "description": "Extract quarter from date",
        "use_cases": ["quarter", "by quarter", "Q1", "Q2"],
        "typical_fields": ["Date"]
    },
    "MONTH": {
        "types": ["DATE", "DATETIME"],
        "description": "Extract month from date",
        "use_cases": ["month", "by month", "monthly"],
        "typical_fields": ["Date", "Order Date"]
    },
    "WEEK": {
        "types": ["DATE", "DATETIME"],
        "description": "Extract week from date",
        "use_cases": ["week", "by week", "weekly"],
        "typical_fields": ["Date"]
    },
    "DAY": {
        "types": ["DATE", "DATETIME"],
        "description": "Extract day from date",
        "use_cases": ["day", "by day", "daily"],
        "typical_fields": ["Date"]
    },
    "TRUNC_YEAR": {
        "types": ["DATE", "DATETIME"],
        "description": "Truncate to year",
        "use_cases": ["year", "truncate year"],
        "typical_fields": ["Date"]
    },
    "TRUNC_QUARTER": {
        "types": ["DATE", "DATETIME"],
        "description": "Truncate to quarter",
        "use_cases": ["quarter", "truncate quarter"],
        "typical_fields": ["Date"]
    },
    "TRUNC_MONTH": {
        "types": ["DATE", "DATETIME"],
        "description": "Truncate to month",
        "use_cases": ["month", "truncate month"],
        "typical_fields": ["Date"]
    },
    "TRUNC_WEEK": {
        "types": ["DATE", "DATETIME"],
        "description": "Truncate to week",
        "use_cases": ["week", "truncate week"],
        "typical_fields": ["Date"]
    },
    "TRUNC_DAY": {
        "types": ["DATE", "DATETIME"],
        "description": "Truncate to day",
        "use_cases": ["day", "truncate day"],
        "typical_fields": ["Date"]
    },
    # Special aggregations
    "AGG": {
        "types": ["*"],
        "description": "Use default aggregation",
        "use_cases": ["default", "auto"],
        "typical_fields": []
    },
    "NONE": {
        "types": ["*"],
        "description": "No aggregation",
        "use_cases": ["none", "raw"],
        "typical_fields": []
    },
    "UNSPECIFIED": {
        "types": ["*"],
        "description": "Unspecified aggregation",
        "use_cases": [],
        "typical_fields": []
    }
}

# Common query patterns for VizQL
VIZQL_QUERY_PATTERNS = [
    {
        "pattern": "total {measure} by {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "SUM"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "total sales by region",
        "description": "Sum a measure grouped by a dimension"
    },
    {
        "pattern": "average {measure} per {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "AVG"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "average price per category",
        "description": "Average a measure grouped by a dimension"
    },
    {
        "pattern": "count of {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{dimension}", "function": "COUNT"}
            ]
        },
        "example": "count of orders",
        "description": "Count rows grouped by a dimension"
    },
    {
        "pattern": "distinct count of {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{dimension}", "function": "COUNTD"}
            ]
        },
        "example": "distinct count of customers",
        "description": "Count distinct values of a dimension"
    },
    {
        "pattern": "min {field} by {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{field}", "function": "MIN"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "min price by category",
        "description": "Minimum value grouped by dimension"
    },
    {
        "pattern": "max {field} by {dimension}",
        "template": {
            "fields": [
                {"fieldCaption": "{field}", "function": "MAX"},
                {"fieldCaption": "{dimension}"}
            ]
        },
        "example": "max sales by region",
        "description": "Maximum value grouped by dimension"
    },
    {
        "pattern": "{measure} by {dimension1} and {dimension2}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "SUM"},
                {"fieldCaption": "{dimension1}"},
                {"fieldCaption": "{dimension2}"}
            ]
        },
        "example": "sales by region and category",
        "description": "Multiple dimensions with a measure"
    },
    {
        "pattern": "top {n} {dimension} by {measure}",
        "template": {
            "fields": [
                {"fieldCaption": "{measure}", "function": "SUM"},
                {"fieldCaption": "{dimension}"}
            ],
            "options": {
                "rowLimit": "{n}"
            }
        },
        "example": "top 10 customers by revenue",
        "description": "Top N values by measure"
    }
]


def suggest_aggregation(field_name: str, field_type: str, field_role: Optional[str] = None) -> str:
    """
    Suggest appropriate aggregation function based on field semantics.
    
    Args:
        field_name: Name of the field (e.g., "Total Sales", "Customer ID")
        field_type: Data type (e.g., "REAL", "STRING", "INTEGER")
        field_role: Field role if available ("MEASURE", "DIMENSION")
    
    Returns:
        Suggested aggregation function name (e.g., "SUM", "AVG", "COUNT")
    
    Examples:
        >>> suggest_aggregation("Total Sales", "REAL")
        'SUM'
        >>> suggest_aggregation("Price", "REAL")
        'AVG'
        >>> suggest_aggregation("Customer ID", "STRING")
        'COUNTD'
        >>> suggest_aggregation("Order Date", "DATE")
        'COUNT'
    """
    field_lower = field_name.lower()
    
    # If field role is DIMENSION, typically use COUNT or COUNTD
    if field_role == "DIMENSION":
        if "id" in field_lower or "key" in field_lower:
            return "COUNTD"
        return "COUNT"
    
    # Check use case keywords in field name
    for agg, rules in VIZQL_AGGREGATIONS.items():
        # Skip date/time and special aggregations for this check
        if agg in ["YEAR", "QUARTER", "MONTH", "WEEK", "DAY", 
                   "TRUNC_YEAR", "TRUNC_QUARTER", "TRUNC_MONTH", 
                   "TRUNC_WEEK", "TRUNC_DAY", "AGG", "NONE", "UNSPECIFIED"]:
            continue
        
        # Check if aggregation is compatible with field type
        valid_types = rules["types"]
        if "*" not in valid_types and field_type not in valid_types:
            continue
        
        # Check use case keywords
        if "use_cases" in rules:
            for keyword in rules["use_cases"]:
                if keyword in field_lower:
                    return agg
        
        # Check typical field names
        if "typical_fields" in rules:
            for typical_field in rules["typical_fields"]:
                if typical_field.lower() in field_lower or field_lower in typical_field.lower():
                    return agg
    
    # Default suggestions by type
    if field_type in ["INTEGER", "REAL"]:
        return "SUM"
    elif field_type in ["DATE", "DATETIME"]:
        return "COUNT"
    elif "id" in field_lower or "key" in field_lower:
        return "COUNTD"
    
    return "COUNT"


def validate_aggregation_for_type(agg: str, data_type: str) -> bool:
    """
    Check if an aggregation function is valid for a given data type.
    
    Args:
        agg: Aggregation function name (e.g., "SUM", "AVG")
        data_type: Data type (e.g., "REAL", "STRING", "DATE")
    
    Returns:
        True if aggregation is valid for the data type, False otherwise
    
    Examples:
        >>> validate_aggregation_for_type("SUM", "REAL")
        True
        >>> validate_aggregation_for_type("SUM", "STRING")
        False
        >>> validate_aggregation_for_type("COUNT", "STRING")
        True
        >>> validate_aggregation_for_type("AVG", "DATE")
        False
    """
    if agg not in VIZQL_AGGREGATIONS:
        return False
    
    valid_types = VIZQL_AGGREGATIONS[agg]["types"]
    return "*" in valid_types or data_type in valid_types


def get_field_role_requirements(field_role: str) -> Dict[str, any]:
    """
    Get requirements for a field role.
    
    Args:
        field_role: Field role ("MEASURE", "DIMENSION", "UNKNOWN")
    
    Returns:
        Dictionary with role requirements
    """
    return VIZQL_FIELD_ROLES.get(field_role, VIZQL_FIELD_ROLES["UNKNOWN"])


def is_measure_field(field_role: str) -> bool:
    """Check if field role is a MEASURE."""
    return field_role == "MEASURE"


def is_dimension_field(field_role: str) -> bool:
    """Check if field role is a DIMENSION."""
    return field_role == "DIMENSION"


def get_aggregation_description(agg: str) -> str:
    """Get human-readable description of an aggregation function."""
    if agg in VIZQL_AGGREGATIONS:
        return VIZQL_AGGREGATIONS[agg]["description"]
    return f"Unknown aggregation: {agg}"


def get_compatible_aggregations(data_type: str) -> List[str]:
    """
    Get list of aggregation functions compatible with a data type.
    
    Args:
        data_type: Data type (e.g., "REAL", "STRING", "DATE")
    
    Returns:
        List of compatible aggregation function names
    """
    compatible = []
    for agg, rules in VIZQL_AGGREGATIONS.items():
        valid_types = rules["types"]
        if "*" in valid_types or data_type in valid_types:
            compatible.append(agg)
    return compatible
