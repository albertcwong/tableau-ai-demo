"""Unit tests for Summary agent nodes."""
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.nodes.analyzer import analyze_data_node


@pytest.mark.asyncio
async def test_analyzer_node_basic():
    """Test analyzer with basic numeric data."""
    state: SummaryAgentState = {
        "user_query": "summarize this view",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": ["view-123"],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "view_data": {
            "columns": ["Sales", "Region", "Date"],
            "data": [
                ["1000", "North", "2024-01"],
                ["1200", "South", "2024-02"],
                ["1500", "East", "2024-03"],
                ["1100", "West", "2024-04"],
                ["1300", "North", "2024-05"]
            ],
            "row_count": 5
        },
        "view_metadata": {"id": "view-123", "name": "Sales View"},
        "column_stats": None,
        "trends": [],
        "outliers": [],
        "correlations": None,
        "key_insights": [],
        "recommendations": [],
        "executive_summary": None,
        "detailed_analysis": None
    }
    
    result = await analyze_data_node(state)
    
    # Should have column stats for numeric column (Sales)
    assert result["column_stats"] is not None
    assert "Sales" in result["column_stats"]
    assert result["column_stats"]["Sales"]["mean"] is not None
    
    # Should detect trends if any
    assert isinstance(result["trends"], list)
    
    # Should have outliers list (even if empty)
    assert isinstance(result["outliers"], list)


@pytest.mark.asyncio
async def test_analyzer_node_empty_data():
    """Test analyzer with empty data."""
    state: SummaryAgentState = {
        "user_query": "summarize this view",
        "agent_type": "summary",
        "context_datasources": [],
        "context_views": ["view-123"],
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_thought": None,
        "final_answer": None,
        "error": None,
        "confidence": None,
        "processing_time": None,
        "view_data": {
            "columns": [],
            "data": [],
            "row_count": 0
        },
        "view_metadata": {"id": "view-123", "name": "Empty View"},
        "column_stats": None,
        "trends": [],
        "outliers": [],
        "correlations": None,
        "key_insights": [],
        "recommendations": [],
        "executive_summary": None,
        "detailed_analysis": None
    }
    
    result = await analyze_data_node(state)
    
    # Should handle empty data gracefully
    assert "error" in result or result["column_stats"] is None
    assert isinstance(result["trends"], list)
    assert isinstance(result["outliers"], list)
