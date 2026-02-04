"""Factory for creating LangGraph agent graphs."""
import logging
from typing import Optional
from langgraph.graph import StateGraph

logger = logging.getLogger(__name__)


class AgentGraphFactory:
    """Factory for creating agent graphs."""
    
    @staticmethod
    def create_vizql_graph() -> StateGraph:
        """Create VizQL agent graph.
        
        Returns:
            Compiled StateGraph for VizQL agent
        """
        from app.services.agents.vizql.graph import create_vizql_graph
        return create_vizql_graph()
    
    @staticmethod
    def create_summary_graph() -> StateGraph:
        """Create Summary agent graph.
        
        Returns:
            Compiled StateGraph for Summary agent
        """
        from app.services.agents.summary.graph import create_summary_graph
        return create_summary_graph()
    
    @staticmethod
    def create_general_graph() -> StateGraph:
        """Create General agent graph.
        
        Returns:
            Compiled StateGraph for General agent
            
        Note: This is a stub implementation. Full implementation will be in Sprint 4.
        """
        logger.warning("General graph creation not yet implemented - returning stub")
        # TODO: Implement in Sprint 4
        # from backend.app.services.agents.general.graph import create_general_graph
        # return create_general_graph()
        raise NotImplementedError("General graph will be implemented in Sprint 4")
    
    @staticmethod
    def create_multi_agent_graph() -> StateGraph:
        """Create multi-agent orchestration graph.
        
        Returns:
            Compiled StateGraph for multi-agent orchestration
        """
        from app.services.agents.multi_agent.orchestrator import create_multi_agent_graph
        return create_multi_agent_graph()
    
    @staticmethod
    def create_graph(agent_type: str) -> StateGraph:
        """Create agent graph by type.
        
        Args:
            agent_type: Agent type ('vizql', 'summary', 'general', or 'multi_agent')
            
        Returns:
            Compiled StateGraph for the specified agent type
            
        Raises:
            ValueError: If agent_type is not recognized
        """
        if agent_type == 'vizql':
            return AgentGraphFactory.create_vizql_graph()
        elif agent_type == 'summary':
            return AgentGraphFactory.create_summary_graph()
        elif agent_type == 'general':
            return AgentGraphFactory.create_general_graph()
        elif agent_type == 'multi_agent':
            return AgentGraphFactory.create_multi_agent_graph()
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
