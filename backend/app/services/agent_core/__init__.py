"""Agent Core - pluggable agent graphs. Import from here to run agents without FastAPI/DB."""
from app.services.agents.graph_factory import AgentGraphFactory
from typing import Any, Dict, Optional

__all__ = ["create_graph", "AgentGraphFactory"]


def create_graph(
    agent_type: str,
    version: Optional[str] = None,
    max_build_retries: Optional[int] = None,
    max_execution_retries: Optional[int] = None,
):
    """Create compiled agent graph by type. No DB/HTTP dependencies."""
    return AgentGraphFactory.create_graph(
        agent_type=agent_type,
        version=version,
        max_build_retries=max_build_retries,
        max_execution_retries=max_execution_retries,
    )
