"""Unit tests for Summary agent data_fetcher node and helpers."""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.agents.summary.nodes.data_fetcher import (
    fetch_data_node,
    _filters_from_embedded,
    _extract_from_embedded,
    _sanitize_view_id,
)
from app.services.agents.summary.state import SummaryAgentState


def test_sanitize_view_id():
    """Test _sanitize_view_id strips invalid suffixes."""
    assert _sanitize_view_id("aY37NWdboRrk2fnuL8fpXAAAAJY") == "aY37NWdboRrk2fnuL8fpXAAAAJY"
    assert _sanitize_view_id("aY37NWdboRrk2fnuL8fpXAAAAJY,1:1") == "aY37NWdboRrk2fnuL8fpXAAAAJY"


def test_filters_from_embedded_empty():
    """Test _filters_from_embedded with empty list."""
    assert _filters_from_embedded([]) is None


def test_filters_from_embedded_categorical():
    """Test _filters_from_embedded with categorical appliedValues."""
    filters = [
        {"fieldName": "Region", "appliedValues": [{"value": "West"}, {"value": "East"}]},
    ]
    out = _filters_from_embedded(filters)
    assert out == {"Region": ["West", "East"]}


def test_filters_from_embedded_string_values():
    """Test _filters_from_embedded with string appliedValues."""
    filters = [{"fieldName": "Category", "appliedValues": ["Tech", "Furniture"]}]
    out = _filters_from_embedded(filters)
    assert out == {"Category": ["Tech", "Furniture"]}


def test_filters_from_embedded_range():
    """Test _filters_from_embedded with min/max range."""
    filters = [{"fieldName": "Sales", "minValue": "100", "maxValue": "5000"}]
    out = _filters_from_embedded(filters)
    assert out == {"Sales": "100,5000"}


def test_filters_from_embedded_skips_internal_ids():
    """Test _filters_from_embedded skips Tableau internal ID values that cause parse errors."""
    filters = [
        {"fieldName": "Param", "appliedValues": [{"value": "(aY37NWdboRrk2fnuL8fpXAAAAJY,1:1)"}]},
    ]
    out = _filters_from_embedded(filters)
    assert out is None or "Param" not in out


def test_extract_from_embedded_worksheet():
    """Test _extract_from_embedded for worksheet with summary_data."""
    views_data = {}
    views_metadata = {}
    emb = {
        "sheet_type": "worksheet",
        "active_sheet": {"name": "Sheet1"},
        "summary_data": {
            "columns": ["A", "B"],
            "data": [["1", "2"], ["3", "4"]],
            "row_count": 2,
        },
    }
    rows = _extract_from_embedded("v1", emb, views_data, views_metadata)
    assert rows == 2
    assert views_data["v1"]["row_count"] == 2
    assert views_metadata["v1"]["name"] == "Sheet1"


def test_extract_from_embedded_dashboard():
    """Test _extract_from_embedded for dashboard with sheets_data."""
    views_data = {}
    views_metadata = {}
    emb = {
        "sheet_type": "dashboard",
        "sheets_data": [
            {"sheet_name": "Chart1", "summary_data": {"columns": ["X"], "data": [["1"]], "row_count": 1}},
            {"sheet_name": "Chart2", "summary_data": {"columns": ["Y"], "data": [["a"], ["b"]], "row_count": 2}},
        ],
    }
    rows = _extract_from_embedded("v2", emb, views_data, views_metadata)
    assert rows == 3
    assert "v2_sheet_0" in views_data
    assert "v2_sheet_1" in views_data
    assert views_data["v2_sheet_0"]["row_count"] == 1
    assert views_data["v2_sheet_1"]["row_count"] == 2
    assert views_metadata["v2_sheet_0"]["name"] == "Chart1"
    assert views_metadata["v2_sheet_1"]["name"] == "Chart2"


@pytest.mark.asyncio
async def test_fetch_data_node_with_embedded_state_worksheet():
    """Test fetch_data_node uses embedded_state when present (worksheet)."""
    state: SummaryAgentState = {
        "user_query": "summarize",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": ["view-1"],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "embedded_state": {
            "view-1": {
                "sheet_type": "worksheet",
                "active_sheet": {"name": "Sales"},
                "summary_data": {
                    "columns": ["Region", "Sales"],
                    "data": [["North", "1000"], ["South", "1200"]],
                    "row_count": 2,
                },
                "captured_at": "2024-01-01T00:00:00Z",
            }
        },
        "view_data": None,
        "view_metadata": None,
        "views_data": None,
        "views_metadata": None,
        "column_stats": None,
        "trends": [],
        "outliers": [],
        "correlations": None,
        "key_insights": [],
        "recommendations": [],
        "executive_summary": None,
        "detailed_analysis": None,
    }
    result = await fetch_data_node(state)
    assert result["views_data"]["view-1"]["row_count"] == 2
    assert result["views_data"]["view-1"]["columns"] == ["Region", "Sales"]
    assert "embedded" in str(result["tool_calls"][0]["result"]).lower()


@pytest.mark.asyncio
async def test_fetch_data_node_with_embedded_state_dashboard():
    """Test fetch_data_node uses embedded_state for dashboard (sheets_data)."""
    state: SummaryAgentState = {
        "user_query": "summarize",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": ["dash-1"],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "embedded_state": {
            "dash-1": {
                "sheet_type": "dashboard",
                "sheets_data": [
                    {"sheet_name": "Sheet1", "summary_data": {"columns": ["A"], "data": [["1"]], "row_count": 1}},
                ],
                "captured_at": "2024-01-01T00:00:00Z",
            }
        },
        "view_data": None,
        "view_metadata": None,
        "views_data": None,
        "views_metadata": None,
        "column_stats": None,
        "trends": [],
        "outliers": [],
        "correlations": None,
        "key_insights": [],
        "recommendations": [],
        "executive_summary": None,
        "detailed_analysis": None,
    }
    result = await fetch_data_node(state)
    assert "dash-1_sheet_0" in result["views_data"]
    assert result["views_data"]["dash-1_sheet_0"]["row_count"] == 1
