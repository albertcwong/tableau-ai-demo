"""Start node - returns immediately to kick off frontend timer."""
import logging
from typing import Dict, Any

from app.services.agents.vizql_streamlined.state import StreamlinedVizQLState

logger = logging.getLogger(__name__)


async def start_node(state: StreamlinedVizQLState) -> Dict[str, Any]:
    """
    No-op start node that returns immediately.

    Triggers first state update so the frontend can start the timer
    and show reasoning steps counter before the slower build_query runs.
    """
    logger.info("Streamlined VizQL start node")
    return {
        **state,
        "current_thought": "Starting query analysis...",
    }
