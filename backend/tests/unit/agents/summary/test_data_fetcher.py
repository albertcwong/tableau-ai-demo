"""Unit tests for Summary agent data_fetcher node and helpers."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.agents.summary.nodes.data_fetcher import (
    fetch_data_node,
    _extract_from_embedded,
)
from app.services.agents.summary.state import SummaryAgentState


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


@pytest.mark.asyncio
async def test_fetch_data_node_missing_embedded_state_returns_error():
    """Test fetch_data_node returns error when embedded_state has no data (no REST fallback)."""
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
        "embedded_state": {},
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
    assert result["error"] is not None
    assert "embedded capture" in result["error"].lower()
    assert result["views_data"] == {}
    assert result["tool_calls"][0]["result"] == "error"


@pytest.mark.asyncio
async def test_fetch_data_node_embedded_state_key_fallback():
    """Test embedded_state lookup uses clean_view_id when view_id has suffix (e.g. ,1:1)."""
    state: SummaryAgentState = {
        "user_query": "summarize",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": ["view-1,1:1"],
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
                    "data": [["North", "100"]],
                    "row_count": 1,
                },
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
    assert result["views_data"]["view-1,1:1"]["row_count"] == 1
    assert result["views_metadata"]["view-1,1:1"]["name"] == "Sales"


@pytest.mark.asyncio
async def test_fetch_data_node_embedded_empty_returns_error():
    """When embedded capture returns 0 rows, return error (no REST fallback)."""
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
                "active_sheet": {"name": "Sheet1"},
                "summary_data": {"columns": [], "data": [], "row_count": 0},
            },
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
    assert result["error"] is not None
    assert "embedded capture" in result["error"].lower()
    assert result["views_data"] == {}
    assert result["tool_calls"][0]["result"] == "error"


@pytest.mark.asyncio
async def test_fetch_data_node_capture_error_returns_error():
    """Test fetch_data_node handles capture_error from embedded_state."""
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
                "view_id": "view-1",
                "sheet_type": "worksheet",
                "captured_at": "2024-01-01T00:00:00Z",
                "capture_error": "Failed to get summary data: Tableau 500 error",
            },
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
    assert result["error"] is not None
    assert "capture failed" in result["error"].lower() or "capture_error" in str(result["error"]).lower()
    assert result["views_data"] == {}
    assert result["tool_calls"][0]["result"] == "error"
    assert "capture failed" in result["tool_calls"][0]["error"].lower()


@pytest.mark.asyncio
async def test_fetch_data_node_no_context_views():
    """Test fetch_data_node returns error when no views in context."""
    state: SummaryAgentState = {
        "user_query": "summarize",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": [],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "embedded_state": {},
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
    assert result["error"] == "No view in context. Please add a view first."
    assert result["views_data"] == {}
