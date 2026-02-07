"""Semantic constraint validation for VizQL queries."""
import logging
import difflib
import re
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
    
    def _formula_has_aggregation(self, formula: Optional[str]) -> bool:
        """
        Check if a formula contains aggregation functions.
        
        Args:
            formula: Formula string to check
            
        Returns:
            True if formula contains aggregation functions
        """
        if not formula:
            return False
        
        # Common aggregation functions in Tableau formulas
        aggregation_patterns = [
            r'\bSUM\s*\(',
            r'\bAVG\s*\(',
            r'\bAVERAGE\s*\(',
            r'\bCOUNT\s*\(',
            r'\bCOUNTD\s*\(',
            r'\bMIN\s*\(',
            r'\bMAX\s*\(',
            r'\bMEDIAN\s*\(',
            r'\bSTDEV\s*\(',
            r'\bSTDEVP\s*\(',
            r'\bVAR\s*\(',
            r'\bVARP\s*\(',
            r'\bAGG\s*\(',
        ]
        
        formula_upper = formula.upper()
        for pattern in aggregation_patterns:
            if re.search(pattern, formula_upper):
                return True
        
        return False
    
    def validate_query(self, query: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate query semantics.
        
        Checks:
        - Field names exist in schema
        - MEASURE fields have aggregation functions
        - Aggregation functions are compatible with field data types
        - NOTE: DIMENSION fields CAN have aggregation functions (e.g., COUNT on Customer Name)
        
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
            
            has_function = "function" in field
            function_name = field.get("function", "").upper() if has_function else None
            
            # Check if this is a calculated field in the query
            is_calculated_field = "calculation" in field
            
            # For calculated fields in query, check if calculation formula has aggregation
            if is_calculated_field:
                calculation_formula = field.get("calculation", "")
                if self._formula_has_aggregation(calculation_formula):
                    # Calculated field already has aggregation - should not have a function field
                    if has_function:
                        errors.append(
                            f"Calculated field '{field_caption}' already contains aggregation in its formula. "
                            f"Remove the 'function' field - calculated fields with aggregation should be used directly."
                        )
                        suggestions.append(
                            f"Remove function from '{field_caption}': "
                            f"{{\"fieldCaption\": \"{field_caption}\", \"calculation\": \"{calculation_formula}\"}}"
                        )
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
            
            # Check if this is an existing calculated field from schema that has aggregation in formula
            field_formula = field_meta.get("formula")
            has_aggregation_in_formula = False
            
            # Check if field has a formula with aggregation
            if field_formula:
                if self._formula_has_aggregation(field_formula):
                    has_aggregation_in_formula = True
                    # Existing calculated field already has aggregation - should not have a function field
                    if has_function:
                        errors.append(
                            f"Field '{field_caption}' is a calculated field that already contains aggregation in its formula. "
                            f"Remove the 'function' field - calculated fields with aggregation should be used directly."
                        )
                        suggestions.append(
                            f"Remove function from '{field_caption}': "
                            f"{{\"fieldCaption\": \"{field_caption}\"}}"
                        )
                        continue
            else:
                # Log when formula is missing for debugging (especially for calculated fields)
                column_class = field_meta.get("columnClass", "")
                if column_class in ["CALCULATION", "TABLE_CALCULATION"]:
                    logger.debug(
                        f"Field '{field_caption}' is a calculated field (columnClass={column_class}) "
                        f"but formula is not available in enriched schema"
                    )
            
            # Check if this is a calculated field (by columnClass)
            # Calculated fields may already have aggregation in their formula, so skip aggregation requirement
            column_class = field_meta.get("columnClass", "")
            is_calculated_field = column_class in ["CALCULATION", "TABLE_CALCULATION"]
            
            # CRITICAL: Measures must have aggregation
            # BUT: Skip this check if:
            # 1. The field already has aggregation in its formula, OR
            # 2. The field is a calculated field (which may have aggregation even if formula not available)
            if field_meta.get("fieldRole") == "MEASURE" and not has_function and not has_aggregation_in_formula and not is_calculated_field:
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
            
            # NOTE: Dimensions CAN have aggregation functions (e.g., COUNT on Customer Name)
            # The VDS API allows aggregations on dimensions, so we don't restrict this.
            # Aggregation compatibility is still validated below via validate_aggregation_for_type()
            
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
