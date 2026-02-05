"""State definition for Summary agent."""
from typing import TypedDict, Optional
from app.services.agents.base_state import BaseAgentState


class SummaryAgentState(BaseAgentState):
    """State for Summary agent graph."""
    
    # View data (backward compatibility - single view)
    view_data: Optional[dict]
    view_metadata: Optional[dict]
    
    # Multiple views support
    views_data: Optional[dict]  # Dict mapping view_id -> view_data
    views_metadata: Optional[dict]  # Dict mapping view_id -> view_metadata
    
    # Analysis results
    column_stats: Optional[dict]  # Mean, median, std dev for numeric columns (can be dict of view_id -> stats for multiple views)
    trends: list[dict]  # Detected trends (includes view_id and view_name for multi-view)
    outliers: list[dict]  # Outlier detection results (includes view_id and view_name for multi-view)
    correlations: Optional[dict]  # Column correlations (can be dict of view_id -> correlations for multiple views)
    
    # Insights
    key_insights: list[str]
    recommendations: list[str]
    
    # Output
    executive_summary: Optional[str]
    detailed_analysis: Optional[str]
