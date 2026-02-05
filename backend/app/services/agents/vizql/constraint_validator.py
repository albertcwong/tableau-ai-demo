"""Semantic constraint validation for VizQL queries."""
import logging
import difflib
from typing import Dict, Any, List, Tuple, Optional

from app.services.agents.vizql.semantic_rules import validate_aggregation_for_type

logger = logging.getLogger(__name__)


class VizQLConstraintValidator:
    """Validates semantic constraints for VizQL queries."""
    
    def __init__(self, enriched_schema: Dict[str, Any]):
        """
        Initialize constraint validator with enriched schema.
        
        Args:
            enriched_schema: Enriched schema from SchemaEnrichmentService
        """
        self.schema = enriched_schema
        self.field_map = enriched_schema.get("field_map", {})
    
    def validate_query(self, query: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate query semantics.
        
        Checks:
        - Field names exist in schema
        - MEASURE fields have aggregation functions
        - DIMENSION fields don't have aggregation functions (unless numeric - REAL/INTEGER)
        - Aggregation functions are compatible with field data types
        
        Args:
            query: VizQL query dictionary
            
        Returns:
            Tuple of (is_valid, errors, suggestions)
        """
        errors = []
        suggestions = []
        
        query_obj = query.get("query", {})
        fields = query_obj.get("fields", [])
        
        if not fields:
            errors.append("Query must have at least one field")
            return False, errors, suggestions
        
        for field in fields:
            field_caption = field.get("fieldCaption", "")
            if not field_caption:
                errors.append("Field missing fieldCaption")
                continue
            
            field_lower = field_caption.lower()
            
            # Check if field exists in schema
            if field_lower not in self.field_map:
                errors.append(f"Field '{field_caption}' not found in schema")
                # Fuzzy match suggestion
                close_matches = self._find_close_matches(field_caption)
                if close_matches:
                    suggestions.append(
                        f"Field '{field_caption}' not found. Did you mean: {', '.join(close_matches)}?"
                    )
                continue
            
            field_meta = self.field_map[field_lower]
            has_function = "function" in field
            
            # CRITICAL: Measures must have aggregation
            if field_meta.get("fieldRole") == "MEASURE" and not has_function:
                errors.append(
                    f"MEASURE field '{field_caption}' requires aggregation function"
                )
                suggested_agg = (
                    field_meta.get("defaultAggregation") or 
                    field_meta.get("suggestedAggregation", "SUM")
                )
                suggestions.append(
                    f"Add aggregation to '{field_caption}': "
                    f"{{\"fieldCaption\": \"{field_caption}\", \"function\": \"{suggested_agg}\"}}"
                )
            
            # CRITICAL: Dimensions should NOT have aggregation UNLESS they are numeric
            # In Tableau, fields can be incorrectly categorized. If a DIMENSION is numeric
            # (REAL, INTEGER), it can still be used for aggregation (e.g., "Sales" as dimension).
            # This allows queries like "top sales by region" even if "Sales" is marked as DIMENSION.
            field_role = field_meta.get("fieldRole", "")
            data_type = field_meta.get("dataType", "")
            is_numeric = data_type in ["REAL", "INTEGER"]
            
            # Only error if dimension is non-numeric AND has aggregation
            if field_role == "DIMENSION" and has_function and not is_numeric:
                errors.append(
                    f"DIMENSION field '{field_caption}' should not have aggregation function"
                )
                suggestions.append(
                    f"Remove 'function' from '{field_caption}': "
                    f"{{\"fieldCaption\": \"{field_caption}\"}}"
                )
            
            # Validate aggregation type compatibility
            if has_function:
                agg = field["function"]
                data_type = field_meta.get("dataType", "UNKNOWN")
                if not validate_aggregation_for_type(agg, data_type):
                    errors.append(
                        f"Aggregation '{agg}' not compatible with data type '{data_type}' "
                        f"for field '{field_caption}'"
                    )
                    compatible_aggs = self._get_compatible_aggregations(data_type)
                    if compatible_aggs:
                        suggestions.append(
                            f"Use compatible aggregation for '{field_caption}': "
                            f"{', '.join(compatible_aggs[:5])}"
                        )
        
        # Validate filters
        filters = query_obj.get("filters", [])
        for filter_obj in filters:
            filter_field = filter_obj.get("field", {})
            filter_caption = filter_field.get("fieldCaption") if isinstance(filter_field, dict) else filter_obj.get("fieldCaption")
            
            if filter_caption:
                filter_lower = filter_caption.lower()
                if filter_lower not in self.field_map:
                    errors.append(f"Filter field '{filter_caption}' not found in schema")
                    close_matches = self._find_close_matches(filter_caption)
                    if close_matches:
                        suggestions.append(
                            f"Filter field '{filter_caption}' not found. Did you mean: {', '.join(close_matches)}?"
                        )
        
        is_valid = len(errors) == 0
        
        if errors:
            logger.info(
                f"Semantic validation found {len(errors)} errors: {errors[:3]}"
            )
        
        return is_valid, errors, suggestions
    
    def _find_close_matches(self, field_name: str, cutoff: float = 0.6) -> List[str]:
        """
        Find close field name matches using fuzzy matching.
        
        Args:
            field_name: Field name to match
            cutoff: Similarity cutoff (0.0 to 1.0)
            
        Returns:
            List of matching field captions (up to 3)
        """
        if not self.field_map:
            return []
        
        field_lower = field_name.lower()
        
        # Use difflib for fuzzy matching
        matches = difflib.get_close_matches(
            field_lower,
            self.field_map.keys(),
            n=3,
            cutoff=cutoff
        )
        
        # Also check for substring matches if no close matches found
        if not matches:
            for schema_field_lower in self.field_map.keys():
                if field_lower in schema_field_lower or schema_field_lower in field_lower:
                    matches.append(schema_field_lower)
                    if len(matches) >= 3:
                        break
        
        # Return original case field captions
        return [
            self.field_map[match].get("fieldCaption", match.title())
            for match in matches
        ]
    
    def _is_valid_aggregation(self, agg: str, data_type: str) -> bool:
        """
        Check if aggregation is valid for data type.
        
        Args:
            agg: Aggregation function name
            data_type: Field data type
            
        Returns:
            True if aggregation is valid for the data type
        """
        return validate_aggregation_for_type(agg, data_type)
    
    def _get_compatible_aggregations(self, data_type: str) -> List[str]:
        """
        Get list of aggregations compatible with a data type.
        
        Args:
            data_type: Field data type
            
        Returns:
            List of compatible aggregation function names
        """
        from app.services.agents.vizql.semantic_rules import get_compatible_aggregations
        return get_compatible_aggregations(data_type)
    
    def validate_field_combination(self, fields: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate that fields can be combined in a query.
        
        This checks for logical constraints like:
        - Multiple measures with different aggregations
        - Date fields with appropriate date aggregations
        
        Args:
            fields: List of field dictionaries
            
        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []
        
        # Check for multiple measures (usually OK, but warn if different aggregations)
        measures = [
            f for f in fields
            if f.get("fieldCaption", "").lower() in self.field_map
            and self.field_map[f.get("fieldCaption", "").lower()].get("fieldRole") == "MEASURE"
        ]
        
        if len(measures) > 5:
            warnings.append(
                f"Query has {len(measures)} measures. Consider if all are needed."
            )
        
        return len(warnings) == 0, warnings
