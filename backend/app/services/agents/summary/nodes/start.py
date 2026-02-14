"""Start node to signal the beginning of Summary agent analysis."""
from typing import Dict, Any

from app.services.agents.summary.state import SummaryAgentState


async def start_node(state: SummaryAgentState) -> Dict[str, Any]:
    """Signal start of analysis. Emits reasoning step for streaming."""
    return {**state, "current_thought": "Starting analysis..."}
