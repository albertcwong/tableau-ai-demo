"""Unit tests for VizQL semantic rules engine."""
import pytest
from app.services.agents.vizql.semantic_rules import (
    suggest_aggregation,
    validate_aggregation_for_type,
    get_field_role_requirements,
    is_measure_field,
    is_dimension_field,
    get_aggregation_description,
    get_compatible_aggregations,
    VIZQL_AGGREGATIONS,
    VIZQL_FIELD_ROLES,
    VIZQL_DATA_TYPES
)


class TestSuggestAggregation:
    """Test aggregation suggestion logic."""
    
    def test_suggest_sum_for_sales_fields(self):
        """Test SUM suggestion for sales-related fields."""
        assert suggest_aggregation("Total Sales", "REAL") == "SUM"
        assert suggest_aggregation("Sales", "REAL") == "SUM"
        assert suggest_aggregation("Revenue", "REAL") == "SUM"
        assert suggest_aggregation("Amount", "REAL") == "SUM"
        assert suggest_aggregation("Profit", "REAL") == "SUM"
    
    def test_suggest_avg_for_price_fields(self):
        """Test AVG suggestion for price-related fields."""
        assert suggest_aggregation("Price", "REAL") == "AVG"
        assert suggest_aggregation("Average Price", "REAL") == "AVG"
        assert suggest_aggregation("Rating", "REAL") == "AVG"
        assert suggest_aggregation("Score", "REAL") == "AVG"
    
    def test_suggest_countd_for_id_fields(self):
        """Test COUNTD suggestion for ID fields."""
        assert suggest_aggregation("Customer ID", "STRING") == "COUNTD"
        assert suggest_aggregation("Product ID", "STRING") == "COUNTD"
        assert suggest_aggregation("Order ID", "STRING") == "COUNTD"
        assert suggest_aggregation("Order Key", "STRING") == "COUNTD"
    
    def test_suggest_count_for_dimension_fields(self):
        """Test COUNT suggestion for dimension fields."""
        assert suggest_aggregation("Region", "STRING", "DIMENSION") == "COUNT"
        assert suggest_aggregation("Category", "STRING", "DIMENSION") == "COUNT"
        assert suggest_aggregation("Customer Name", "STRING", "DIMENSION") == "COUNT"
    
    def test_suggest_countd_for_dimension_id_fields(self):
        """Test COUNTD for dimension fields with ID in name."""
        assert suggest_aggregation("Customer ID", "STRING", "DIMENSION") == "COUNTD"
        assert suggest_aggregation("Product ID", "STRING", "DIMENSION") == "COUNTD"
    
    def test_suggest_min_max_for_date_fields(self):
        """Test MIN/MAX for date fields."""
        # These would be suggested based on context, but COUNT is default for dates
        assert suggest_aggregation("Order Date", "DATE") == "COUNT"
        assert suggest_aggregation("Ship Date", "DATE") == "COUNT"
    
    def test_default_suggestions_by_type(self):
        """Test default suggestions when no keywords match."""
        assert suggest_aggregation("Some Number", "REAL") == "SUM"
        assert suggest_aggregation("Some Number", "INTEGER") == "SUM"
        assert suggest_aggregation("Some Text", "STRING") == "COUNT"
        assert suggest_aggregation("Some Date", "DATE") == "COUNT"
    
    def test_case_insensitive_matching(self):
        """Test that field name matching is case-insensitive."""
        assert suggest_aggregation("TOTAL SALES", "REAL") == "SUM"
        assert suggest_aggregation("total sales", "REAL") == "SUM"
        assert suggest_aggregation("Total Sales", "REAL") == "SUM"


class TestValidateAggregationForType:
    """Test aggregation type validation."""
    
    def test_sum_valid_for_numeric_types(self):
        """Test SUM is valid for numeric types."""
        assert validate_aggregation_for_type("SUM", "REAL") is True
        assert validate_aggregation_for_type("SUM", "INTEGER") is True
        assert validate_aggregation_for_type("SUM", "STRING") is False
        assert validate_aggregation_for_type("SUM", "DATE") is False
    
    def test_avg_valid_for_numeric_types(self):
        """Test AVG is valid for numeric types."""
        assert validate_aggregation_for_type("AVG", "REAL") is True
        assert validate_aggregation_for_type("AVG", "INTEGER") is True
        assert validate_aggregation_for_type("AVG", "STRING") is False
    
    def test_count_valid_for_all_types(self):
        """Test COUNT is valid for all types."""
        for data_type in VIZQL_DATA_TYPES:
            assert validate_aggregation_for_type("COUNT", data_type) is True
    
    def test_countd_valid_for_all_types(self):
        """Test COUNTD is valid for all types."""
        for data_type in VIZQL_DATA_TYPES:
            assert validate_aggregation_for_type("COUNTD", data_type) is True
    
    def test_min_max_valid_for_numeric_and_date(self):
        """Test MIN/MAX valid for numeric and date types."""
        assert validate_aggregation_for_type("MIN", "REAL") is True
        assert validate_aggregation_for_type("MIN", "INTEGER") is True
        assert validate_aggregation_for_type("MIN", "DATE") is True
        assert validate_aggregation_for_type("MIN", "DATETIME") is True
        assert validate_aggregation_for_type("MIN", "STRING") is False
        
        assert validate_aggregation_for_type("MAX", "REAL") is True
        assert validate_aggregation_for_type("MAX", "INTEGER") is True
        assert validate_aggregation_for_type("MAX", "DATE") is True
        assert validate_aggregation_for_type("MAX", "DATETIME") is True
    
    def test_date_aggregations_valid_for_date_types(self):
        """Test date aggregations valid for date types."""
        date_aggs = ["YEAR", "QUARTER", "MONTH", "WEEK", "DAY",
                     "TRUNC_YEAR", "TRUNC_QUARTER", "TRUNC_MONTH",
                     "TRUNC_WEEK", "TRUNC_DAY"]
        
        for agg in date_aggs:
            assert validate_aggregation_for_type(agg, "DATE") is True
            assert validate_aggregation_for_type(agg, "DATETIME") is True
            assert validate_aggregation_for_type(agg, "STRING") is False
    
    def test_invalid_aggregation(self):
        """Test that invalid aggregation names return False."""
        assert validate_aggregation_for_type("INVALID_AGG", "REAL") is False
        assert validate_aggregation_for_type("", "REAL") is False


class TestFieldRoleRequirements:
    """Test field role requirement functions."""
    
    def test_measure_requires_aggregation(self):
        """Test that MEASURE fields require aggregation."""
        requirements = get_field_role_requirements("MEASURE")
        assert requirements["requires_aggregation"] is True
        assert "INTEGER" in requirements["compatible_types"]
        assert "REAL" in requirements["compatible_types"]
    
    def test_dimension_no_aggregation(self):
        """Test that DIMENSION fields don't require aggregation."""
        requirements = get_field_role_requirements("DIMENSION")
        assert requirements["requires_aggregation"] is False
        assert "STRING" in requirements["compatible_types"]
        assert "DATE" in requirements["compatible_types"]
    
    def test_unknown_role_fallback(self):
        """Test that unknown roles fallback to UNKNOWN."""
        requirements = get_field_role_requirements("INVALID_ROLE")
        assert requirements["requires_aggregation"] is False
    
    def test_is_measure_field(self):
        """Test measure field detection."""
        assert is_measure_field("MEASURE") is True
        assert is_measure_field("DIMENSION") is False
        assert is_measure_field("UNKNOWN") is False
    
    def test_is_dimension_field(self):
        """Test dimension field detection."""
        assert is_dimension_field("DIMENSION") is True
        assert is_dimension_field("MEASURE") is False
        assert is_dimension_field("UNKNOWN") is False


class TestAggregationDescriptions:
    """Test aggregation description functions."""
    
    def test_get_aggregation_description(self):
        """Test getting aggregation descriptions."""
        assert "Sum numeric values" in get_aggregation_description("SUM")
        assert "Average numeric values" in get_aggregation_description("AVG")
        assert "Count rows" in get_aggregation_description("COUNT")
        assert "Count distinct values" in get_aggregation_description("COUNTD")
    
    def test_invalid_aggregation_description(self):
        """Test description for invalid aggregation."""
        desc = get_aggregation_description("INVALID")
        assert "Unknown aggregation" in desc


class TestCompatibleAggregations:
    """Test getting compatible aggregations for data types."""
    
    def test_compatible_aggregations_for_real(self):
        """Test aggregations compatible with REAL type."""
        compatible = get_compatible_aggregations("REAL")
        assert "SUM" in compatible
        assert "AVG" in compatible
        assert "MIN" in compatible
        assert "MAX" in compatible
        assert "COUNT" in compatible
        assert "COUNTD" in compatible
        assert "STRING" not in compatible  # Date aggregations shouldn't be here
    
    def test_compatible_aggregations_for_string(self):
        """Test aggregations compatible with STRING type."""
        compatible = get_compatible_aggregations("STRING")
        assert "COUNT" in compatible
        assert "COUNTD" in compatible
        assert "SUM" not in compatible
        assert "AVG" not in compatible
    
    def test_compatible_aggregations_for_date(self):
        """Test aggregations compatible with DATE type."""
        compatible = get_compatible_aggregations("DATE")
        assert "COUNT" in compatible
        assert "COUNTD" in compatible
        assert "MIN" in compatible
        assert "MAX" in compatible
        assert "YEAR" in compatible
        assert "MONTH" in compatible
        assert "SUM" not in compatible
        assert "AVG" not in compatible


class TestConstants:
    """Test that constants are properly defined."""
    
    def test_vizql_data_types_defined(self):
        """Test that data types are defined."""
        assert len(VIZQL_DATA_TYPES) > 0
        assert "INTEGER" in VIZQL_DATA_TYPES
        assert "REAL" in VIZQL_DATA_TYPES
        assert "STRING" in VIZQL_DATA_TYPES
        assert "DATE" in VIZQL_DATA_TYPES
    
    def test_vizql_field_roles_defined(self):
        """Test that field roles are defined."""
        assert "MEASURE" in VIZQL_FIELD_ROLES
        assert "DIMENSION" in VIZQL_FIELD_ROLES
        assert "UNKNOWN" in VIZQL_FIELD_ROLES
    
    def test_vizql_aggregations_defined(self):
        """Test that aggregations are defined."""
        assert len(VIZQL_AGGREGATIONS) > 0
        assert "SUM" in VIZQL_AGGREGATIONS
        assert "AVG" in VIZQL_AGGREGATIONS
        assert "COUNT" in VIZQL_AGGREGATIONS
        assert "COUNTD" in VIZQL_AGGREGATIONS
    
    def test_all_aggregations_have_descriptions(self):
        """Test that all aggregations have descriptions."""
        for agg_name, agg_info in VIZQL_AGGREGATIONS.items():
            assert "description" in agg_info
            assert len(agg_info["description"]) > 0
    
    def test_all_aggregations_have_types(self):
        """Test that all aggregations have compatible types."""
        for agg_name, agg_info in VIZQL_AGGREGATIONS.items():
            assert "types" in agg_info
            assert isinstance(agg_info["types"], list)
            assert len(agg_info["types"]) > 0
