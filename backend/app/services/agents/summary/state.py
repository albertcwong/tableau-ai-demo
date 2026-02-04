"""State definition for Summary agent."""
from typing import TypedDict, Optional
from app.services.agents.base_state import BaseAgentState


class SummaryAgentState(BaseAgentState):
    """State for Summary agent graph."""
    
    # View data
    view_data: Optional[dict]
    view_metadata: Optional[dict]
    
    # Analysis results
    column_stats: Optional[dict]  # Mean, median, std dev for numeric columns
    trends: list[dict]  # Detected trends
    outliers: list[dict]  # Outlier detection results
    correlations: Optional[dict]  # Column correlations
    
    # Insights
    key_insights: list[str]
    recommendations: list[str]
    
    # Output
    executive_summary: Optional[str]
    detailed_analysis: Optional[str]
