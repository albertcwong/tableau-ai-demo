"""Self-reflection and critique utilities for agents."""
import logging
from typing import Dict, Any, List, Optional
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class SelfReflectionCritic:
    """Implements self-reflection and critique for agent outputs."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """Initialize critic.
        
        Args:
            api_key: API key for AI client
            model: Model to use for critique
        """
        self.api_key = api_key
        self.model = model
        self.ai_client = UnifiedAIClient(
            gateway_url=settings.BACKEND_API_URL,
            api_key=api_key
        )
    
    async def critique_output(
        self,
        original_query: str,
        agent_output: Dict[str, Any],
        agent_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Critique agent output and suggest improvements.
        
        Args:
            original_query: Original user query
            agent_output: Output from agent
            agent_type: Type of agent that produced output
            context: Optional context
            
        Returns:
            Critique with suggestions and score
        """
        critique_prompt = self._build_critique_prompt(
            original_query=original_query,
            agent_output=agent_output,
            agent_type=agent_type,
            context=context
        )
        
        response = await self.ai_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_critique_system_prompt(agent_type)},
                {"role": "user", "content": critique_prompt}
            ]
        )
        
        critique = self._parse_critique(response.content)
        
        return {
            "critique": critique,
            "score": critique.get("score", 0.5),
            "suggestions": critique.get("suggestions", []),
            "issues": critique.get("issues", []),
            "improvements": critique.get("improvements", [])
        }
    
    async def reflect_on_execution(
        self,
        execution_trace: List[Dict[str, Any]],
        final_output: Dict[str, Any],
        original_query: str
    ) -> Dict[str, Any]:
        """Reflect on agent execution and identify areas for improvement.
        
        Args:
            execution_trace: Trace of execution steps
            final_output: Final output from agent
            original_query: Original user query
            
        Returns:
            Reflection with insights and recommendations
        """
        reflection_prompt = f"""Reflect on this agent execution and provide insights.

Original Query: {original_query}

Execution Trace:
"""
        for i, step in enumerate(execution_trace, 1):
            reflection_prompt += f"\nStep {i}: {step.get('agent_type', 'unknown')} - {step.get('action', '')}"
            if step.get("error"):
                reflection_prompt += f" [ERROR: {step.get('error')}]"
            if step.get("result"):
                reflection_prompt += f"\n  Result: {str(step.get('result'))[:200]}"

        reflection_prompt += f"""

Final Output: {str(final_output)[:500]}

Provide reflection on:
1. What went well?
2. What could be improved?
3. Were there any unnecessary steps?
4. Could the execution have been more efficient?
5. Did the output fully address the query?
"""

        response = await self.ai_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a reflective assistant that analyzes agent executions and provides constructive feedback."},
                {"role": "user", "content": reflection_prompt}
            ]
        )
        
        reflection = self._parse_reflection(response.content)
        
        return {
            "reflection": reflection,
            "what_went_well": reflection.get("what_went_well", []),
            "improvements": reflection.get("improvements", []),
            "efficiency_notes": reflection.get("efficiency_notes", []),
            "completeness_score": reflection.get("completeness_score", 0.5)
        }
    
    def _build_critique_prompt(
        self,
        original_query: str,
        agent_output: Dict[str, Any],
        agent_type: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build critique prompt."""
        prompt = f"""Critique this agent output.

Original Query: {original_query}
Agent Type: {agent_type}

Agent Output:
{self._format_output(agent_output)}

"""
        if context:
            prompt += f"Context: {self._format_context(context)}\n\n"
        
        prompt += """Evaluate the output on:
1. Accuracy: Does it correctly address the query?
2. Completeness: Is all necessary information included?
3. Clarity: Is it clear and understandable?
4. Relevance: Is it relevant to the query?
5. Quality: Overall quality of the response

Provide:
- A score from 0.0 to 1.0
- Specific issues found (if any)
- Suggestions for improvement
- What was done well"""
        
        return prompt
    
    def _get_critique_system_prompt(self, agent_type: str) -> str:
        """Get system prompt for critique."""
        agent_specific = {
            "vizql": "Focus on query correctness, field names, aggregations, and result accuracy.",
            "summary": "Focus on insight quality, statistical accuracy, and summary completeness.",
            "general": "Focus on answer relevance, clarity, and completeness."
        }
        
        base = "You are a critical reviewer of agent outputs. Be constructive but thorough."
        specific = agent_specific.get(agent_type, "")
        
        return f"{base}\n{specific}"
    
    def _parse_critique(self, response: str) -> Dict[str, Any]:
        """Parse critique from response."""
        critique = {
            "score": 0.5,
            "issues": [],
            "suggestions": [],
            "improvements": [],
            "strengths": []
        }
        
        # Try to extract structured information
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if "score:" in line_lower or "rating:" in line_lower:
                # Try to extract score
                import re
                score_match = re.search(r'(\d+\.?\d*)', line)
                if score_match:
                    try:
                        score = float(score_match.group(1))
                        if score > 1.0:
                            score = score / 10.0  # Normalize if out of 10
                        critique["score"] = min(1.0, max(0.0, score))
                    except ValueError:
                        pass
            
            if "issue" in line_lower or "problem" in line_lower:
                current_section = "issues"
            elif "suggestion" in line_lower or "improve" in line_lower:
                current_section = "suggestions"
            elif "strength" in line_lower or "well" in line_lower:
                current_section = "strengths"
            elif line.strip().startswith("-") or line.strip().startswith("*"):
                item = line.strip().lstrip("-*").strip()
                if current_section == "issues":
                    critique["issues"].append(item)
                elif current_section == "suggestions":
                    critique["suggestions"].append(item)
                elif current_section == "strengths":
                    critique["strengths"].append(item)
        
        # If no structured parsing, use full response
        if not critique["issues"] and not critique["suggestions"]:
            critique["full_critique"] = response
        
        return critique
    
    def _parse_reflection(self, response: str) -> Dict[str, Any]:
        """Parse reflection from response."""
        reflection = {
            "what_went_well": [],
            "improvements": [],
            "efficiency_notes": [],
            "completeness_score": 0.5
        }
        
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if "went well" in line_lower or "good" in line_lower:
                current_section = "what_went_well"
            elif "improve" in line_lower or "better" in line_lower:
                current_section = "improvements"
            elif "efficien" in line_lower or "optimize" in line_lower:
                current_section = "efficiency_notes"
            elif "complete" in line_lower and "score" in line_lower:
                import re
                score_match = re.search(r'(\d+\.?\d*)', line)
                if score_match:
                    try:
                        score = float(score_match.group(1))
                        if score > 1.0:
                            score = score / 10.0
                        reflection["completeness_score"] = min(1.0, max(0.0, score))
                    except ValueError:
                        pass
            elif line.strip().startswith("-") or line.strip().startswith("*") or line.strip()[0].isdigit():
                item = line.strip().lstrip("-*0123456789.").strip()
                if current_section == "what_went_well" and item:
                    reflection["what_went_well"].append(item)
                elif current_section == "improvements" and item:
                    reflection["improvements"].append(item)
                elif current_section == "efficiency_notes" and item:
                    reflection["efficiency_notes"].append(item)
        
        if not reflection["what_went_well"] and not reflection["improvements"]:
            reflection["full_reflection"] = response
        
        return reflection
    
    def _format_output(self, output: Dict[str, Any]) -> str:
        """Format agent output for prompt."""
        parts = []
        if "final_answer" in output:
            parts.append(f"Final Answer: {output['final_answer']}")
        if "query_results" in output:
            parts.append(f"Query Results: {str(output['query_results'])[:300]}")
        if "insights" in output:
            parts.append(f"Insights: {output['insights']}")
        if "error" in output:
            parts.append(f"Error: {output['error']}")
        return "\n".join(parts) if parts else str(output)[:500]
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt."""
        parts = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                parts.append(f"{key}: {str(value)[:200]}")
            else:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
