"""Unit tests for VizQL agent nodes."""
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.agents.vizql.state import VizQLAgentState
from app.services.agents.vizql.nodes.validator import validate_query_node


@pytest.mark.asyncio
async def test_validator_node_valid_query():
    """Test validator with valid query."""
    state: VizQLAgentState = {
        "user_query": "show sales by region",
        "agent_type": "vizql",
        "context_datasources": ["ds-123"],
        "context_views": [],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "schema": {
            "columns": [
                {"name": "Sales", "data_type": "number", "is_measure": True},
                {"name": "Region", "data_type": "string", "is_dimension": True}
            ]
        },
        "required_measures": [],
        "required_dimensions": [],
        "required_filters": {},
        "query_draft": {
            "datasource": {"datasourceLuid": "ds-123"},
            "query": {
                "fields": [
                    {"fieldCaption": "Sales", "function": "SUM"},
                    {"fieldCaption": "Region"}
                ]
            },
            "options": {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        },
        "query_version": 1,
        "is_valid": False,
        "validation_errors": [],
        "validation_suggestions": [],
        "query_results": None,
        "execution_error": None
    }
    
    result = await validate_query_node(state)
    
    assert result["is_valid"] == True
    assert len(result["validation_errors"]) == 0


@pytest.mark.asyncio
async def test_validator_node_invalid_field():
    """Test validator with invalid field name."""
    state: VizQLAgentState = {
        "user_query": "show sales by region",
        "agent_type": "vizql",
        "context_datasources": ["ds-123"],
        "context_views": [],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "schema": {
            "columns": [
                {"name": "Total Sales", "data_type": "number", "is_measure": True},
                {"name": "Sales Region", "data_type": "string", "is_dimension": True}
            ]
        },
        "required_measures": [],
        "required_dimensions": [],
        "required_filters": {},
        "query_draft": {
            "datasource": {"datasourceLuid": "ds-123"},
            "query": {
                "fields": [
                    {"fieldCaption": "Sales", "function": "SUM"},  # Wrong field name
                    {"fieldCaption": "Region"}  # Wrong field name
                ]
            },
            "options": {
                "returnFormat": "OBJECTS",
                "disaggregate": False
            }
        },
        "query_version": 1,
        "is_valid": False,
        "validation_errors": [],
        "validation_suggestions": [],
        "query_results": None,
        "execution_error": None
    }
    
    result = await validate_query_node(state)
    
    assert result["is_valid"] == False
    assert len(result["validation_errors"]) > 0
    assert len(result["validation_suggestions"]) > 0  # Should suggest correct field names
