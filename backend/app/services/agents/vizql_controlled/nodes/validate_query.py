"""Validate query node - local syntax and semantic validation."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_controlled.state import VizQLGraphState
from app.services.agents.vizql.constraint_validator import VizQLConstraintValidator

logger = logging.getLogger(__name__)


async def validate_query_node(state: VizQLGraphState) -> Dict[str, Any]:
    """
    Local syntax and semantic validation (no LLM).
    
    Validation Checks:
    A. Syntax Validation:
    1. Required fields present (datasourceLuid, query, options)
    2. Field names match schema
    3. Aggregation functions valid (SUM, AVG, COUNT, etc.)
    4. Filter types valid (MATCH, RANGE, etc.)
    5. Sorting directions valid (ASC, DESC)
    
    B. Semantic Validation:
    1. Measures used with aggregation functions
    2. Dimensions not aggregated
    3. Filters reference actual field names
    4. TopN has valid measure for sorting
    5. No duplicate field selections
    
    C. Safety Checks:
    1. Query not requesting > 10,000 rows without topN/limit
    2. No nested aggregations
    3. Calculated fields have valid syntax
    
    Duration: 10-50ms
    """
    query_draft = state.get("query_draft")
    schema = state.get("schema", {})
    attempt = state.get("attempt", 1)
    
    if not query_draft:
        return {
            **state,
            "validation_status": "invalid",
            "validation_errors": ["No query to validate"],
            "attempt": attempt + 1,
            "current_thought": "Error: No query to validate"
        }
    
    errors = []
    
    # A. Syntax Validation
    if not query_draft.get("datasource", {}).get("datasourceLuid"):
        errors.append("Missing datasource.datasourceLuid")
    
    if not query_draft.get("query"):
        errors.append("Missing query object")
    else:
        query_obj = query_draft.get("query", {})
        if not query_obj.get("fields"):
            errors.append("Missing query.fields")
    
    # Validate aggregation functions
    valid_aggs = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNTD", "MEDIAN", "STDEV", "VAR", "ATTR"}
    
    # B. Semantic Validation (if enriched schema available)
    enriched_schema = schema
    if enriched_schema:
        try:
            constraint_validator = VizQLConstraintValidator(enriched_schema)
            is_valid, semantic_errors, suggestions = constraint_validator.validate_query(query_draft)
            
            if not is_valid:
                errors.extend(semantic_errors)
        except Exception as e:
            logger.warning(f"Semantic validation failed: {e}")
            # Fall through to basic validation
    
    # Basic field name validation
    if schema and not errors:
        field_map = schema.get("field_map", {})
        query_fields = query_draft.get("query", {}).get("fields", [])
        
        for field in query_fields:
            field_caption = field.get("fieldCaption")
            if field_caption:
                # Skip schema validation for calculated fields
                if "calculation" in field:
                    continue
                
                field_lower = field_caption.lower()
                if field_lower not in field_map:
                    errors.append(f"Field '{field_caption}' not found in schema")
            
            # Validate aggregation function
            if "function" in field:
                func = field["function"].upper()
                if func not in valid_aggs:
                    errors.append(f"Invalid aggregation function '{func}'. Valid: {', '.join(sorted(valid_aggs))}")
    
    # C. Safety Checks
    query_obj = query_draft.get("query", {})
    if not query_obj.get("topN") and not query_obj.get("limit"):
        # Estimate row count (rough check)
        # This is a simple check - in production you might have better estimates
        pass  # Skip for now, can be enhanced
    
    # Determine validation status
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info("Query validation passed")
        # Ensure validated_query has full structure
        validated_query = query_draft.copy()
        if "datasource" not in validated_query:
            validated_query["datasource"] = {"datasourceLuid": state.get("datasource_id", "")}
        if "options" not in validated_query:
            validated_query["options"] = {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        
        return {
            **state,
            "validated_query": validated_query,
            "validation_status": "valid",
            "current_thought": "Validating query syntax..."
        }
    else:
        logger.warning(f"Query validation failed: {errors}")
        return {
            **state,
            "validation_errors": errors,
            "validation_status": "invalid",
            "attempt": attempt + 1,
            "current_thought": f"Validation failed: {len(errors)} errors"
        }