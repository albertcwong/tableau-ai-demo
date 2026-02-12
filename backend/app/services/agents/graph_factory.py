"""Factory for creating LangGraph agent graphs."""
import logging
from typing import Optional
from langgraph.graph import StateGraph

logger = logging.getLogger(__name__)


class AgentGraphFactory:
    """Factory for creating agent graphs."""
    
    @staticmethod
    def create_vizql_graph(
        version: str = "v3",
        max_build_retries: Optional[int] = None,
        max_execution_retries: Optional[int] = None
    ) -> StateGraph:
        """Create VizQL agent graph.
        
        Args:
            version: Version string ('v1', 'v2', 'v3'). Defaults to 'v3'.
            max_build_retries: Optional max build retries (for v3). Falls back to settings if not provided.
            max_execution_retries: Optional max execution retries (for v3). Falls back to settings if not provided.
        
        Returns:
            Compiled StateGraph for VizQL agent
            
        Raises:
            ValueError: If version is not recognized
        """
        if version == "v3":
            from app.services.agents.vizql_streamlined.graph import create_streamlined_vizql_graph
            # Pass retry config to graph creation
            return create_streamlined_vizql_graph(
                max_build_retries=max_build_retries,
                max_execution_retries=max_execution_retries
            )
        elif version == "v2":
            from app.services.agents.vizql_tool_use.graph import get_vizql_tool_use_agent
            return get_vizql_tool_use_agent()
        elif version == "v1":
            from app.services.agents.vizql.graph import create_vizql_graph
            return create_vizql_graph()
        else:
            raise ValueError(f"Unknown VizQL version: {version}. Valid versions: v1, v2, v3")
    
    @staticmethod
    def create_summary_graph() -> StateGraph:
        """Create Summary agent graph.
        
        Returns:
            Compiled StateGraph for Summary agent
        """
        from app.services.agents.summary.graph import create_summary_graph
        return create_summary_graph()
    
    @staticmethod
    def create_multi_agent_graph() -> StateGraph:
        """Create multi-agent orchestration graph.
        
        Returns:
            Compiled StateGraph for multi-agent orchestration
        """
        from app.services.agents.multi_agent.orchestrator import create_multi_agent_graph
        return create_multi_agent_graph()
    
    @staticmethod
    def create_graph(
        agent_type: str,
        version: Optional[str] = None,
        max_build_retries: Optional[int] = None,
        max_execution_retries: Optional[int] = None
    ) -> StateGraph:
        """Create agent graph by type.
        
        Args:
            agent_type: Agent type ('vizql', 'summary', or 'multi_agent')
            version: Optional version string (for vizql: 'v1', 'v2', 'v3')
            max_build_retries: Optional max build retries (for vizql v3)
            max_execution_retries: Optional max execution retries (for vizql v3)
            
        Returns:
            Compiled StateGraph for the specified agent type
            
        Raises:
            ValueError: If agent_type is not recognized
        """
        if agent_type == 'vizql':
            return AgentGraphFactory.create_vizql_graph(
                version=version or "v3",
                max_build_retries=max_build_retries,
                max_execution_retries=max_execution_retries
            )
        elif agent_type == 'summary':
            return AgentGraphFactory.create_summary_graph()
        elif agent_type == 'multi_agent':
            return AgentGraphFactory.create_multi_agent_graph()
        else:
            raise ValueError(f"Unknown agent type: {agent_type}. Valid types: vizql, summary, multi_agent")
