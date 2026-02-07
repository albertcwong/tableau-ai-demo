"""Build compressed, token-efficient context for LLM."""
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Maximum fields to include in compressed context (to avoid token limits)
MAX_FIELDS_IN_CONTEXT = 200


def build_compressed_schema_context(enriched_schema: Dict[str, Any]) -> str:
    """
    Build compressed schema format for LLM.
    
    Format: FieldName (TYPE) [ROLE] {defaultAgg}
    Example: Total Sales (REAL) [MEASURE] {default: SUM}
    
    Args:
        enriched_schema: Enriched schema from SchemaEnrichmentService
        
    Returns:
        Compressed schema string for LLM prompt
    """
    if not enriched_schema or not enriched_schema.get("fields"):
        return "## Available Fields\nNo fields available."
    
    lines = ["## Available Fields\n"]
    
    fields = enriched_schema["fields"]
    
    # Limit fields to avoid token overflow
    if len(fields) > MAX_FIELDS_IN_CONTEXT:
        logger.warning(
            f"Truncating {len(fields)} fields to {MAX_FIELDS_IN_CONTEXT} "
            "most relevant fields for context"
        )
        # Prioritize non-hidden fields, then measures, then dimensions
        visible_fields = [f for f in fields if not f.get("hidden")]
        measures = [f for f in visible_fields if f.get("fieldRole") == "MEASURE"]
        dimensions = [f for f in visible_fields if f.get("fieldRole") == "DIMENSION"]
        
        # Take up to MAX_FIELDS_IN_CONTEXT, prioritizing measures
        fields_to_include = measures[:MAX_FIELDS_IN_CONTEXT // 2]
        remaining = MAX_FIELDS_IN_CONTEXT - len(fields_to_include)
        fields_to_include.extend(dimensions[:remaining])
        
        if len(fields_to_include) < len(visible_fields):
            logger.info(
                f"Including {len(fields_to_include)} of {len(visible_fields)} visible fields "
                f"({len(measures)} measures, {len(dimensions)} dimensions)"
            )
        fields = fields_to_include
    
    for field in fields:
        if field.get("hidden"):
            continue
        
        field_caption = field.get("fieldCaption", "")
        if not field_caption:
            continue
        
        # Base format: FieldName (TYPE) [ROLE]
        line = f"- {field_caption} ({field.get('dataType', 'UNKNOWN')}) [{field.get('fieldRole', 'UNKNOWN')}]"
        
        # Add aggregation hint for measures
        if field.get("fieldRole") == "MEASURE":
            agg = field.get("defaultAggregation") or field.get("suggestedAggregation", "SUM")
            line += f" {{default: {agg}}}"
        
        # Add description if available (truncated to 50 chars)
        description = field.get("description", "")
        if description:
            desc_short = description[:50] + "..." if len(description) > 50 else description
            line += f" - {desc_short}"
        
        lines.append(line)
    
    if len(lines) == 1:  # Only header, no fields
        lines.append("No fields available.")
    
    return "\n".join(lines)


def build_semantic_hints(enriched_schema: Dict[str, Any]) -> str:
    """
    Build semantic hints section for LLM prompt.
    
    Args:
        enriched_schema: Enriched schema from SchemaEnrichmentService
        
    Returns:
        Semantic hints string
    """
    if not enriched_schema:
        return "## Query Construction Hints\nNo schema available."
    
    measures = enriched_schema.get("measures", [])
    dimensions = enriched_schema.get("dimensions", [])
    
    hints = [
        "## Query Construction Hints\n",
        f"**Measures ({len(measures)}):** Require aggregation functions (SUM, AVG, COUNT, etc.)",
    ]
    
    # Show first 10 measures
    if measures:
        measures_preview = measures[:10]
        hints.append(f"Available: {', '.join(measures_preview)}")
        if len(measures) > 10:
            hints.append(f"... and {len(measures) - 10} more")
    else:
        hints.append("None available")
    
    hints.append("")
    hints.append(f"**Dimensions ({len(dimensions)}):** Used for grouping. Non-numeric dimensions (STRING/DATE/BOOLEAN) don't use aggregation. Numeric dimensions (REAL/INTEGER) can use aggregation if needed.")
    
    # Show first 10 dimensions
    if dimensions:
        dimensions_preview = dimensions[:10]
        hints.append(f"Available: {', '.join(dimensions_preview)}")
        if len(dimensions) > 10:
            hints.append(f"... and {len(dimensions) - 10} more")
    else:
        hints.append("None available")
    
    return "\n".join(hints)


def build_field_lookup_hints(enriched_schema: Dict[str, Any], user_query: str) -> str:
    """
    Build field lookup hints based on user query keywords.
    
    This helps the LLM match user intent to actual field names.
    
    Args:
        enriched_schema: Enriched schema
        user_query: User's natural language query
        
    Returns:
        Field lookup hints string
    """
    if not enriched_schema or not enriched_schema.get("field_map"):
        return ""
    
    field_map = enriched_schema["field_map"]
    user_lower = user_query.lower()
    
    # Extract potential field keywords from user query
    keywords = []
    common_field_keywords = [
        "sales", "revenue", "profit", "cost", "price", "amount", "quantity",
        "region", "category", "state", "country", "customer", "product",
        "date", "year", "month", "order", "transaction"
    ]
    
    for keyword in common_field_keywords:
        if keyword in user_lower:
            keywords.append(keyword)
    
    if not keywords:
        return ""
    
    # Find matching fields
    matching_fields = []
    for keyword in keywords:
        for field_lower, field_info in field_map.items():
            if keyword in field_lower and field_info.get("fieldCaption") not in [f[0] for f in matching_fields]:
                matching_fields.append((
                    field_info.get("fieldCaption"),
                    field_info.get("fieldRole"),
                    field_info.get("dataType")
                ))
                if len(matching_fields) >= 10:  # Limit matches
                    break
        if len(matching_fields) >= 10:
            break
    
    if not matching_fields:
        return ""
    
    hints = ["## Field Matching Hints\n"]
    hints.append("Based on your query, here are relevant fields:")
    
    for field_caption, field_role, data_type in matching_fields[:5]:  # Show top 5
        role_hint = " (requires aggregation)" if field_role == "MEASURE" else " (for grouping)"
        hints.append(f"- {field_caption} ({data_type}){role_hint}")
    
    return "\n".join(hints)


def build_full_compressed_context(
    enriched_schema: Dict[str, Any],
    user_query: str,
    required_measures: List[str] = None,
    required_dimensions: List[str] = None,
    required_filters: Dict[str, Any] = None,
    topN: Dict[str, Any] = None,
    sorting: List[Dict[str, Any]] = None,
    calculations: List[Dict[str, Any]] = None,
    bins: List[Dict[str, Any]] = None
) -> str:
    """
    Build complete compressed context for query construction.
    
    Combines compressed schema, semantic hints, and field lookup hints.
    
    Args:
        enriched_schema: Enriched schema from SchemaEnrichmentService
        user_query: User's natural language query
        required_measures: List of measure names from intent parsing
        required_dimensions: List of dimension names from intent parsing
        required_filters: Filter requirements from intent parsing (structured with filterType and params)
        topN: Top N pattern information
        sorting: Sorting requirements
        calculations: Ad-hoc calculation requirements
        bins: Bin requirements
        
    Returns:
        Complete compressed context string
    """
    parts = []
    
    # Add compressed schema
    parts.append(build_compressed_schema_context(enriched_schema))
    parts.append("")
    
    # Add semantic hints
    parts.append(build_semantic_hints(enriched_schema))
    parts.append("")
    
    # Add field lookup hints if user query provided
    if user_query:
        lookup_hints = build_field_lookup_hints(enriched_schema, user_query)
        if lookup_hints:
            parts.append(lookup_hints)
            parts.append("")
    
    # Add intent summary if provided
    has_patterns = (
        required_measures or required_dimensions or 
        (topN and topN.get("enabled")) or
        (required_filters and len(required_filters) > 0) or
        (sorting and len(sorting) > 0) or
        (calculations and len(calculations) > 0) or
        (bins and len(bins) > 0)
    )
    
    if has_patterns:
        parts.append("## Parsed Intent")
        
        if required_measures:
            parts.append(f"Measures requested: {', '.join(required_measures)}")
        if required_dimensions:
            parts.append(f"Dimensions requested: {', '.join(required_dimensions)}")
        
        # Top N Pattern (CRITICAL)
        if topN and topN.get("enabled"):
            parts.append("")
            parts.append("**CRITICAL: TOP N PATTERN DETECTED**")
            parts.append(f"User wants top/bottom {topN.get('howMany', 'N')} {topN.get('dimensionField', 'dimension')} by {topN.get('measureField', 'measure')}")
            parts.append(f"Direction: {topN.get('direction', 'TOP')}")
            parts.append("**YOU MUST USE TOP FILTER, NOT SORTING!**")
            parts.append("Example filter structure:")
            parts.append(json.dumps({
                "field": {"fieldCaption": topN.get("dimensionField", "DimensionName")},
                "filterType": "TOP",
                "howMany": topN.get("howMany", 10),
                "direction": topN.get("direction", "TOP"),
                "fieldToMeasure": {
                    "fieldCaption": topN.get("measureField", "MeasureName"),
                    "function": "SUM"
                }
            }, indent=2))
        
        # Filter Patterns
        if required_filters:
            parts.append("")
            parts.append("**FILTER PATTERNS DETECTED**")
            for field_name, filter_info in required_filters.items():
                if isinstance(filter_info, dict):
                    filter_type = filter_info.get("filterType", "UNKNOWN")
                    params = filter_info.get("params", {})
                    
                    parts.append(f"\n**Filter on '{field_name}':**")
                    parts.append(f"  Filter Type: {filter_type}")
                    
                    if filter_type == "DATE":
                        parts.append(f"  Period Type: {params.get('periodType', 'N/A')}")
                        parts.append(f"  Date Range Type: {params.get('dateRangeType', 'N/A')}")
                        if params.get("rangeN"):
                            parts.append(f"  Range N: {params.get('rangeN')}")
                        parts.append("  Example structure:")
                        parts.append(json.dumps({
                            "field": {"fieldCaption": field_name},
                            "filterType": "DATE",
                            "periodType": params.get("periodType", "MONTHS"),
                            "dateRangeType": params.get("dateRangeType", "LASTN"),
                            "rangeN": params.get("rangeN", 3)
                        }, indent=4))
                    
                    elif filter_type == "MATCH":
                        parts.append("  Match parameters:")
                        if params.get("contains"):
                            parts.append(f"    contains: '{params.get('contains')}'")
                        if params.get("startsWith"):
                            parts.append(f"    startsWith: '{params.get('startsWith')}'")
                        if params.get("endsWith"):
                            parts.append(f"    endsWith: '{params.get('endsWith')}'")
                        parts.append("  Example structure:")
                        parts.append(json.dumps({
                            "field": {"fieldCaption": field_name},
                            "filterType": "MATCH",
                            "contains": params.get("contains"),
                            "exclude": params.get("exclude", False)
                        }, indent=4))
                    
                    elif filter_type == "SET":
                        parts.append(f"  Values: {params.get('values', [])}")
                        parts.append(f"  Exclude: {params.get('exclude', False)}")
                        parts.append("  Example structure:")
                        parts.append(json.dumps({
                            "field": {"fieldCaption": field_name},
                            "filterType": "SET",
                            "values": params.get("values", []),
                            "exclude": params.get("exclude", False)
                        }, indent=4))
                    
                    elif filter_type == "QUANTITATIVE_NUMERICAL":
                        parts.append(f"  Quantitative Type: {params.get('quantitativeFilterType', 'N/A')}")
                        if params.get("min") is not None:
                            parts.append(f"  Min: {params.get('min')}")
                        if params.get("max") is not None:
                            parts.append(f"  Max: {params.get('max')}")
                        parts.append("  Example structure:")
                        parts.append(json.dumps({
                            "field": {"fieldCaption": field_name},
                            "filterType": "QUANTITATIVE_NUMERICAL",
                            "quantitativeFilterType": params.get("quantitativeFilterType", "MIN"),
                            "min": params.get("min")
                        }, indent=4))
                    
                    elif filter_type == "QUANTITATIVE_DATE":
                        parts.append(f"  Quantitative Type: {params.get('quantitativeFilterType', 'N/A')}")
                        if params.get("minDate"):
                            parts.append(f"  Min Date: {params.get('minDate')}")
                        if params.get("maxDate"):
                            parts.append(f"  Max Date: {params.get('maxDate')}")
                        parts.append("  Example structure:")
                        parts.append(json.dumps({
                            "field": {"fieldCaption": field_name},
                            "filterType": "QUANTITATIVE_DATE",
                            "quantitativeFilterType": params.get("quantitativeFilterType", "RANGE"),
                            "minDate": params.get("minDate"),
                            "maxDate": params.get("maxDate")
                        }, indent=4))
        
        # Calculations
        if calculations and len(calculations) > 0:
            parts.append("")
            parts.append("**CALCULATIONS DETECTED**")
            parts.append("**IMPORTANT**: Only include these calculations if the user explicitly requested them!")
            for calc in calculations:
                parts.append(f"- {calc.get('fieldCaption', 'calculated_field')}: {calc.get('formula', 'N/A')}")
            parts.append("Add these as fields with 'calculation' property ONLY if user asked for them:")
            parts.append(json.dumps(calculations, indent=2))
        
        # Bins
        if bins and len(bins) > 0:
            parts.append("")
            parts.append("**BINS DETECTED**")
            for bin_info in bins:
                parts.append(f"- {bin_info.get('fieldCaption', 'field')} with binSize: {bin_info.get('binSize', 'N/A')}")
            parts.append("Add binSize property to measure fields:")
            parts.append(json.dumps(bins, indent=2))
        
        # Sorting (only if not Top N)
        if sorting and len(sorting) > 0 and not (topN and topN.get("enabled")):
            parts.append("")
            parts.append("**SORTING REQUIRED**")
            for sort_info in sorting:
                parts.append(f"- {sort_info.get('field', 'field')}: {sort_info.get('direction', 'ASC')} (priority: {sort_info.get('priority', 1)})")
            parts.append("Add sortPriority and sortDirection to fields:")
            parts.append(json.dumps(sorting, indent=2))
        
        parts.append("")
    
    return "\n".join(parts)
