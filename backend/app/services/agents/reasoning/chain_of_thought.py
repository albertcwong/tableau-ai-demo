"""Chain-of-thought prompting utilities for advanced reasoning."""
import logging
from typing import Dict, Any, List, Optional
from app.services.ai.client import UnifiedAIClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class ChainOfThoughtReasoner:
    """Implements chain-of-thought reasoning for agents."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """Initialize reasoner.
        
        Args:
            api_key: API key for AI client
            model: Model to use for reasoning
        """
        self.api_key = api_key
        self.model = model
        self.ai_client = UnifiedAIClient(
            gateway_url=settings.GATEWAY_BASE_URL,
            api_key=api_key
        )
    
    async def reason_step_by_step(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = 5
    ) -> Dict[str, Any]:
        """Perform chain-of-thought reasoning step by step.
        
        Args:
            query: The question or task to reason about
            context: Optional context (schema, data, etc.)
            max_steps: Maximum reasoning steps
            
        Returns:
            Dictionary with reasoning steps and final conclusion
        """
        reasoning_steps = []
        current_thought = query
        
        for step_num in range(max_steps):
            step_prompt = self._build_reasoning_prompt(
                query=query,
                current_thought=current_thought,
                previous_steps=reasoning_steps,
                context=context,
                step_num=step_num
            )
            
            response = await self.ai_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_cot_system_prompt()},
                    {"role": "user", "content": step_prompt}
                ]
            )
            
            # Parse response for reasoning step
            step_result = self._parse_reasoning_step(response.content)
            reasoning_steps.append(step_result)
            
            # Check if we've reached a conclusion
            if step_result.get("conclusion") or step_result.get("is_final"):
                break
            
            current_thought = step_result.get("thought", "")
        
        # Generate final conclusion if not reached
        if not reasoning_steps[-1].get("conclusion"):
            conclusion = await self._generate_conclusion(query, reasoning_steps)
        else:
            conclusion = reasoning_steps[-1].get("conclusion")
        
        return {
            "query": query,
            "reasoning_steps": reasoning_steps,
            "conclusion": conclusion,
            "num_steps": len(reasoning_steps)
        }
    
    def _build_reasoning_prompt(
        self,
        query: str,
        current_thought: str,
        previous_steps: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
        step_num: int
    ) -> str:
        """Build prompt for next reasoning step."""
        prompt_parts = [f"Original Query: {query}\n"]
        
        if context:
            prompt_parts.append(f"Context: {self._format_context(context)}\n")
        
        if previous_steps:
            prompt_parts.append("Previous Reasoning Steps:\n")
            for i, step in enumerate(previous_steps, 1):
                prompt_parts.append(f"Step {i}: {step.get('thought', '')}")
                if step.get("observation"):
                    prompt_parts.append(f"  Observation: {step.get('observation')}")
            prompt_parts.append("")
        
        prompt_parts.append(
            f"Current Step {step_num + 1}: Think step by step about the next logical step.\n"
            "Provide:\n"
            "1. Your thought/reasoning\n"
            "2. Any observations or facts you've identified\n"
            "3. Whether you've reached a conclusion (yes/no)\n"
            "4. If yes, what is your conclusion?"
        )
        
        return "\n".join(prompt_parts)
    
    def _get_cot_system_prompt(self) -> str:
        """Get system prompt for chain-of-thought reasoning."""
        return """You are a reasoning assistant that thinks step by step.

Your task is to break down complex problems into smaller steps and reason through them systematically.

For each step:
1. State your thought process clearly
2. Identify any observations or facts
3. Determine if you have enough information to conclude
4. If yes, state your conclusion clearly

Think carefully and methodically. Don't jump to conclusions without reasoning through the steps."""
    
    def _parse_reasoning_step(self, response: str) -> Dict[str, Any]:
        """Parse reasoning step from AI response."""
        # Simple parsing - look for structured markers
        step = {
            "thought": response,
            "observation": None,
            "conclusion": None,
            "is_final": False
        }
        
        # Try to extract structured parts
        lines = response.split("\n")
        current_section = "thought"
        thought_parts = []
        
        for line in lines:
            line_lower = line.lower().strip()
            if "observation:" in line_lower or "fact:" in line_lower:
                step["observation"] = line.split(":", 1)[-1].strip()
                current_section = "observation"
            elif "conclusion:" in line_lower or "answer:" in line_lower:
                step["conclusion"] = line.split(":", 1)[-1].strip()
                step["is_final"] = True
                current_section = "conclusion"
            elif "yes" in line_lower and ("conclude" in line_lower or "final" in line_lower):
                step["is_final"] = True
            else:
                if current_section == "thought":
                    thought_parts.append(line)
        
        if thought_parts:
            step["thought"] = "\n".join(thought_parts).strip()
        
        return step
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt."""
        parts = []
        if "schema" in context:
            parts.append(f"Schema: {context['schema']}")
        if "data" in context:
            parts.append(f"Data: {str(context['data'])[:500]}")  # Truncate
        if "datasources" in context:
            parts.append(f"Datasources: {context['datasources']}")
        if "views" in context:
            parts.append(f"Views: {context['views']}")
        return "\n".join(parts)
    
    async def _generate_conclusion(
        self,
        query: str,
        reasoning_steps: List[Dict[str, Any]]
    ) -> str:
        """Generate final conclusion from reasoning steps."""
        conclusion_prompt = f"""Based on the following reasoning steps, provide a clear conclusion.

Original Query: {query}

Reasoning Steps:
"""
        for i, step in enumerate(reasoning_steps, 1):
            conclusion_prompt += f"\nStep {i}: {step.get('thought', '')}"
            if step.get("observation"):
                conclusion_prompt += f"\n  Observation: {step.get('observation')}"
        
        conclusion_prompt += "\n\nProvide a clear, concise conclusion based on the reasoning above."
        
        response = await self.ai_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a conclusion generator. Provide clear, concise conclusions based on reasoning steps."},
                {"role": "user", "content": conclusion_prompt}
            ]
        )
        
        return response.content.strip()


def add_cot_to_prompt(base_prompt: str, reasoning_steps: Optional[List[str]] = None) -> str:
    """Add chain-of-thought instructions to a prompt.
    
    Args:
        base_prompt: Base prompt text
        reasoning_steps: Optional list of reasoning steps to include
        
    Returns:
        Enhanced prompt with chain-of-thought instructions
    """
    cot_instruction = """
Think step by step:
1. Break down the problem into smaller parts
2. Consider each part carefully
3. Combine your reasoning to reach a conclusion
4. Explain your reasoning process
"""
    
    if reasoning_steps:
        cot_instruction += "\nExample reasoning steps:\n"
        for i, step in enumerate(reasoning_steps, 1):
            cot_instruction += f"{i}. {step}\n"
    
    return base_prompt + "\n\n" + cot_instruction
