"""Validator node for validating VizQL queries."""
import logging
import difflib
from typing import Dict, Any

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState
from app.services.agents.vizql.constraint_validator import VizQLConstraintValidator
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql_streamlined", "validator")
async def validate_query_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    Validate VizQL query against schema.
    
    This is a local validation step (no LLM).
    """
    query = state.get("query_draft")
    schema = state.get("schema")
    
    if not query:
        return {
            **state,
            "is_valid": False,
            "validation_errors": ["No query to validate"],
            "validation_suggestions": []
        }
    
    if not schema:
        return {
            **state,
            "is_valid": False,
            "validation_errors": ["No schema available for validation"],
            "validation_suggestions": []
        }
    
    errors = []
    suggestions = []
    
    # Basic structure validation
    if not query.get("datasource", {}).get("datasourceLuid"):
        errors.append("Missing datasource.datasourceLuid")
    
    if not query.get("query", {}).get("fields"):
        errors.append("Missing query.fields")
    
    # Check if we have enriched schema for semantic validation
    enriched_schema = state.get("enriched_schema")
    
    if enriched_schema:
        # Use semantic constraint validator
        logger.info("Using semantic constraint validator with enriched schema")
        try:
            constraint_validator = VizQLConstraintValidator(enriched_schema)
            is_semantically_valid, semantic_errors, semantic_suggestions = \
                constraint_validator.validate_query(query)
            
            # Combine semantic errors and suggestions
            errors.extend(semantic_errors)
            suggestions.extend(semantic_suggestions)
            
            # Also validate field combination (warnings only)
            fields = query.get("query", {}).get("fields", [])
            _, combination_warnings = constraint_validator.validate_field_combination(fields)
            if combination_warnings:
                suggestions.extend([f"Note: {w}" for w in combination_warnings])
                
        except Exception as e:
            logger.warning(f"Semantic validation failed, falling back to basic validation: {e}")
            # Fall through to basic validation
    
    # Basic validation (always runs, or as fallback)
    schema_fields = {}
    for col in schema.get("columns", []):
        field_name = col.get("name", "")
        if field_name:
            schema_fields[field_name.lower()] = col
    
    # Validate field names (if not already validated semantically)
    if not enriched_schema:
        valid_aggs = {
            "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNTD", "MEDIAN", "STDEV", "VAR", "ATTR",
            # Date functions for temporal grouping
            "TRUNC_YEAR", "TRUNC_QUARTER", "TRUNC_MONTH", "TRUNC_WEEK", "TRUNC_DAY",
            "YEAR", "QUARTER", "MONTH", "WEEK", "DAY"
        }
        
        for field in query.get("query", {}).get("fields", []):
            field_name = field.get("fieldCaption")
            if not field_name:
                if "Field missing fieldCaption" not in errors:
                    errors.append("Field missing fieldCaption")
                continue
            
            # Skip schema validation for calculated fields
            if "calculation" in field:
                continue
            
            # Check if field exists in schema (case-insensitive)
            field_lower = field_name.lower()
            if field_lower not in schema_fields:
                if f"Field '{field_name}' not found in schema" not in errors:
                    errors.append(f"Field '{field_name}' not found in schema")
                    # Fuzzy match suggestion
                    close_matches_lower = difflib.get_close_matches(field_lower, schema_fields.keys(), n=3, cutoff=0.4)
                    
                    # Also check for substring matches
                    if not close_matches_lower:
                        for schema_field_lower in schema_fields.keys():
                            if field_lower in schema_field_lower or schema_field_lower in field_lower:
                                close_matches_lower.append(schema_field_lower)
                                if len(close_matches_lower) >= 3:
                                    break
                    
                    if close_matches_lower:
                        original_names = [schema_fields[match].get("name", match.title()) for match in close_matches_lower[:3]]
                        suggestions.append(f"Field '{field_name}' not found. Did you mean: {', '.join(original_names)}?")
            
            # Validate aggregation functions (basic check)
            if "function" in field:
                func = field["function"].upper()
                if func not in valid_aggs:
                    error_msg = f"Invalid aggregation function '{func}' for field '{field_name}'. Valid: {', '.join(sorted(valid_aggs))}"
                    if error_msg not in errors:
                        errors.append(error_msg)
                
                # Check if field is a calculated field with aggregation in formula
                # This check requires enriched schema, so skip if not available
                if enriched_schema:
                    field_lower = field_name.lower()
                    field_map = enriched_schema.get("field_map", {})
                    if field_lower in field_map:
                        field_meta = field_map[field_lower]
                        field_formula = field_meta.get("formula")
                        if field_formula:
                            # Check if formula contains aggregation functions
                            import re
                            aggregation_patterns = [
                                r'\bSUM\s*\(', r'\bAVG\s*\(', r'\bAVERAGE\s*\(', r'\bCOUNT\s*\(', r'\bCOUNTD\s*\(',
                                r'\bMIN\s*\(', r'\bMAX\s*\(', r'\bMEDIAN\s*\(', r'\bSTDEV\s*\(', r'\bVAR\s*\(',
                            ]
                            formula_upper = field_formula.upper()
                            has_agg_in_formula = any(re.search(pattern, formula_upper) for pattern in aggregation_patterns)
                            
                            if has_agg_in_formula:
                                error_msg = f"Field '{field_name}' is a calculated field that already contains aggregation in its formula. Remove the 'function' field - calculated fields with aggregation should be used directly."
                                if error_msg not in errors:
                                    errors.append(error_msg)
                                    suggestions.append(
                                        f"Remove function from '{field_name}': "
                                        f"{{\"fieldCaption\": \"{field_name}\"}}"
                                    )
        
        # Validate filters (basic check)
        for filter_obj in query.get("query", {}).get("filters", []):
            filter_field = filter_obj.get("fieldCaption")
            if filter_field:
                filter_field_lower = filter_field.lower()
                if filter_field_lower not in schema_fields:
                    if f"Filter field '{filter_field}' not found in schema" not in errors:
                        errors.append(f"Filter field '{filter_field}' not found in schema")
                        close_matches_lower = difflib.get_close_matches(filter_field_lower, schema_fields.keys(), n=3, cutoff=0.4)
                        
                        if not close_matches_lower:
                            for schema_field_lower in schema_fields.keys():
                                if filter_field_lower in schema_field_lower or schema_field_lower in filter_field_lower:
                                    close_matches_lower.append(schema_field_lower)
                                    if len(close_matches_lower) >= 3:
                                        break
                        
                        if close_matches_lower:
                            original_names = [schema_fields[match].get("name", match.title()) for match in close_matches_lower[:3]]
                            suggestions.append(f"Filter field '{filter_field}' not found. Did you mean: {', '.join(original_names)}?")
    
    is_valid = len(errors) == 0
    
    return {
        **state,
        "is_valid": is_valid,
        "validation_errors": errors,
        "validation_suggestions": suggestions,
        "current_thought": f"Validation {'passed' if is_valid else 'failed'} with {len(errors)} errors"
    }
