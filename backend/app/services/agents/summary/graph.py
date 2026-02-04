"""Summary agent graph implementation."""
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.nodes.data_fetcher import fetch_data_node
from app.services.agents.summary.nodes.analyzer import analyze_data_node
from app.services.agents.summary.nodes.insight_gen import generate_insights_node
from app.services.agents.summary.nodes.summarizer import summarize_node

logger = logging.getLogger(__name__)


def create_summary_graph() -> StateGraph:
    """
    Create Summary agent graph with analysis pipeline.
    
    Graph flow:
    1. Data Fetcher -> Analyzer -> Insight Generator -> Summarizer -> END
    2. Error handling at each step terminates early
    """
    workflow = StateGraph(SummaryAgentState)
    
    # Add nodes
    workflow.add_node("data_fetcher", fetch_data_node)
    workflow.add_node("analyzer", analyze_data_node)
    workflow.add_node("insight_gen", generate_insights_node)
    workflow.add_node("summarizer", summarize_node)
    
    # Set entry point
    workflow.set_entry_point("data_fetcher")
    
    # Add edges (linear flow)
    workflow.add_edge("data_fetcher", "analyzer")
    workflow.add_edge("analyzer", "insight_gen")
    workflow.add_edge("insight_gen", "summarizer")
    workflow.add_edge("summarizer", END)
    
    # Compile with checkpointing for resumability
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
