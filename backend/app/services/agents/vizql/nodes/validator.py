"""Validator node for validating VizQL queries."""
import json
import logging
import difflib
from typing import Dict, Any

from app.services.agents.vizql.state import VizQLAgentState
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


@track_node_execution("vizql", "validator")
async def validate_query_node(state: VizQLAgentState) -> Dict[str, Any]:
    """
    Validate VizQL query against schema.
    
    This is an "Observe" step in ReAct.
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
    
    # Get schema field names
    schema_fields = {}
    for col in schema.get("columns", []):
        field_name = col.get("name", "")
        if field_name:
            schema_fields[field_name.lower()] = col
    
    # Validation checks
    if not query.get("datasource", {}).get("datasourceLuid"):
        errors.append("Missing datasource.datasourceLuid")
    
    if not query.get("query", {}).get("fields"):
        errors.append("Missing query.fields")
    
        # Validate field names
    valid_aggs = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNTD", "MEDIAN", "STDEV", "VAR", "ATTR"}
    
    for field in query.get("query", {}).get("fields", []):
        field_name = field.get("fieldCaption")
        if not field_name:
            errors.append("Field missing fieldCaption")
            continue
        
        # Check if field exists in schema (case-insensitive)
        field_lower = field_name.lower()
        if field_lower not in schema_fields:
            errors.append(f"Field '{field_name}' not found in schema")
            # Fuzzy match suggestion - use lower cutoff and check substring matches
            close_matches_lower = difflib.get_close_matches(field_lower, schema_fields.keys(), n=3, cutoff=0.4)
            
            # Also check for substring matches (e.g., "Sales" in "Total Sales")
            if not close_matches_lower:
                for schema_field_lower in schema_fields.keys():
                    if field_lower in schema_field_lower or schema_field_lower in field_lower:
                        close_matches_lower.append(schema_field_lower)
                        if len(close_matches_lower) >= 3:
                            break
            
            if close_matches_lower:
                # Get original case field names from schema
                original_names = [schema_fields[match].get("name", match.title()) for match in close_matches_lower[:3]]
                suggestions.append(f"Field '{field_name}' not found. Did you mean: {', '.join(original_names)}?")
        
        # Validate aggregation functions
        if "function" in field:
            func = field["function"].upper()
            if func not in valid_aggs:
                errors.append(f"Invalid aggregation function '{func}' for field '{field_name}'. Valid: {', '.join(sorted(valid_aggs))}")
    
    # Validate filters
    for filter_obj in query.get("query", {}).get("filters", []):
        filter_field = filter_obj.get("fieldCaption")
        if filter_field:
            filter_field_lower = filter_field.lower()
            if filter_field_lower not in schema_fields:
                errors.append(f"Filter field '{filter_field}' not found in schema")
                close_matches_lower = difflib.get_close_matches(filter_field_lower, schema_fields.keys(), n=3, cutoff=0.4)
                
                # Also check for substring matches
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
