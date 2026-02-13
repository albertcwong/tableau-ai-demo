"""Summary agent graph implementation."""
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.agents.summary.state import SummaryAgentState
from app.services.agents.summary.nodes.data_fetcher import fetch_data_node
from app.services.agents.summary.nodes.summarizer import summarize_node

logger = logging.getLogger(__name__)


def create_summary_graph() -> StateGraph:
    """
    Create Summary agent graph with data-first pipeline.
    
    Graph flow:
    1. Data Fetcher (embedded_state or REST fallback) -> Summarizer -> END
    """
    workflow = StateGraph(SummaryAgentState)
    workflow.add_node("data_fetcher", fetch_data_node)
    workflow.add_node("summarizer", summarize_node)
    workflow.set_entry_point("data_fetcher")
    workflow.add_edge("data_fetcher", "summarizer")
    workflow.add_edge("summarizer", END)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
