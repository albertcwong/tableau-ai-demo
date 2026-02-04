"""Meta-agent for intelligent agent selection."""
import logging
from typing import Dict, Any, Optional, List
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class MetaAgentSelector:
    """Intelligent agent selector using AI to choose the best agent."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """Initialize meta-agent selector.
        
        Args:
            api_key: API key for AI client
            model: Model to use for selection
        """
        self.api_key = api_key
        self.model = model
        self.ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
    
    async def select_agent(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
        available_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Select the best agent for a query using AI reasoning.
        
        Args:
            user_query: User's query
            context: Optional context (datasources, views, conversation history)
            available_agents: Optional list of available agent types
            
        Returns:
            Dictionary with selected agent, confidence, and reasoning
        """
        if available_agents is None:
            available_agents = ["vizql", "summary", "general", "multi_agent"]
        
        selection_prompt = self._build_selection_prompt(
            user_query=user_query,
            context=context,
            available_agents=available_agents
        )
        
        response = await self.ai_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_selection_system_prompt()},
                {"role": "user", "content": selection_prompt}
            ]
        )
        
        selection = self._parse_selection(response.content, available_agents)
        
        return {
            "selected_agent": selection["agent_type"],
            "confidence": selection.get("confidence", 0.5),
            "reasoning": selection.get("reasoning", ""),
            "alternative_agents": selection.get("alternatives", []),
            "requires_multi_agent": selection.get("requires_multi_agent", False)
        }
    
    def _build_selection_prompt(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]],
        available_agents: List[str]
    ) -> str:
        """Build agent selection prompt."""
        prompt = f"""Select the best agent to handle this query.

User Query: {user_query}

Available Agents:
"""
        agent_descriptions = {
            "vizql": "Constructs and executes VizQL queries. Use when user wants to query data, build visualizations, or analyze datasources.",
            "summary": "Summarizes and analyzes view data. Use when user wants insights, summaries, or statistical analysis of existing views.",
            "general": "General purpose chat and analysis. Use for questions, explanations, or tasks that don't fit other agents.",
            "multi_agent": "Orchestrates multiple agents. Use when query requires multiple steps (e.g., query data then summarize it)."
        }
        
        for agent in available_agents:
            desc = agent_descriptions.get(agent, "Unknown agent")
            prompt += f"- {agent}: {desc}\n"
        
        prompt += "\n"
        
        if context:
            prompt += "Context:\n"
            if context.get("datasources"):
                prompt += f"- Datasources available: {context['datasources']}\n"
            if context.get("views"):
                prompt += f"- Views available: {context['views']}\n"
            if context.get("conversation_history"):
                prompt += f"- Previous messages: {len(context['conversation_history'])} messages\n"
            prompt += "\n"
        
        prompt += """Analyze the query and determine:
1. Which agent is best suited? (required)
2. Confidence level (0.0 to 1.0)
3. Reasoning for your choice
4. Alternative agents that could also work (if any)
5. Whether this requires multiple agents working together

Return your response in this format:
Agent: <agent_type>
Confidence: <0.0-1.0>
Reasoning: <explanation>
Alternatives: <comma-separated list or "none">
Multi-Agent: <yes/no>"""
        
        return prompt
    
    def _get_selection_system_prompt(self) -> str:
        """Get system prompt for agent selection."""
        return """You are an intelligent agent selector. Your job is to analyze user queries and select the most appropriate agent to handle them.

Consider:
- The specific task the user wants to accomplish
- The capabilities of each agent
- The context available (datasources, views, etc.)
- Whether multiple agents are needed

Be precise and provide clear reasoning for your selection."""
    
    def _parse_selection(
        self,
        response: str,
        available_agents: List[str]
    ) -> Dict[str, Any]:
        """Parse agent selection from response."""
        selection = {
            "agent_type": "general",  # Default fallback
            "confidence": 0.5,
            "reasoning": response,
            "alternatives": [],
            "requires_multi_agent": False
        }
        
        lines = response.split("\n")
        for line in lines:
            line_lower = line.lower().strip()
            
            if line_lower.startswith("agent:"):
                agent = line.split(":", 1)[-1].strip().lower()
                # Validate agent is available
                if agent in available_agents:
                    selection["agent_type"] = agent
                elif "multi" in agent or "multi_agent" in agent:
                    selection["agent_type"] = "multi_agent"
                    selection["requires_multi_agent"] = True
            
            elif line_lower.startswith("confidence:"):
                import re
                conf_match = re.search(r'(\d+\.?\d*)', line)
                if conf_match:
                    try:
                        conf = float(conf_match.group(1))
                        if conf > 1.0:
                            conf = conf / 10.0
                        selection["confidence"] = min(1.0, max(0.0, conf))
                    except ValueError:
                        pass
            
            elif line_lower.startswith("reasoning:"):
                selection["reasoning"] = line.split(":", 1)[-1].strip()
            
            elif line_lower.startswith("alternatives:"):
                alts = line.split(":", 1)[-1].strip()
                if alts.lower() != "none":
                    selection["alternatives"] = [a.strip() for a in alts.split(",")]
            
            elif line_lower.startswith("multi-agent:") or line_lower.startswith("multi_agent:"):
                if "yes" in line_lower:
                    selection["requires_multi_agent"] = True
                    if selection["agent_type"] == "general":
                        selection["agent_type"] = "multi_agent"
        
        return selection
    
    async def select_with_fallback(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
        previous_selection: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Select agent with fallback logic based on previous attempts.
        
        Args:
            user_query: User's query
            context: Optional context
            previous_selection: Previous selection result (if retrying)
            
        Returns:
            Selection result with fallback information
        """
        if previous_selection:
            # If previous selection failed, try alternatives
            alternatives = previous_selection.get("alternative_agents", [])
            if alternatives:
                logger.info(f"Trying alternative agents: {alternatives}")
                # Select from alternatives
                selection = await self.select_agent(
                    user_query=user_query,
                    context=context,
                    available_agents=alternatives
                )
                selection["is_fallback"] = True
                selection["original_selection"] = previous_selection.get("selected_agent")
                return selection
        
        # Normal selection
        return await self.select_agent(user_query, context)
