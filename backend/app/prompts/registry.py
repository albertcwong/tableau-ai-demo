"""Prompt registry for loading and managing agent prompts."""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Centralized prompt management with template support and caching."""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize prompt registry.
        
        Args:
            prompts_dir: Path to prompts directory. Defaults to app/prompts relative to this file.
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent
        
        self.prompts_dir = Path(prompts_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self._cache: Dict[str, str] = {}
        self._cache_times: Dict[str, float] = {}
        self.ttl_seconds = 3600  # 1 hour cache TTL
    
    def get_prompt(
        self,
        prompt_path: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get a prompt with optional variable substitution.
        
        Args:
            prompt_path: Path relative to prompts dir (e.g., "agents/vizql/system.txt")
            variables: Dictionary of variables for template rendering
            
        Returns:
            Rendered prompt string
            
        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        variables = variables or {}
        
        # Create cache key - handle unhashable types (lists, dicts) by converting to JSON string
        try:
            # Try to hash directly if all values are hashable
            cache_key = f"{prompt_path}:{hash(frozenset(variables.items()))}"
        except TypeError:
            # Fall back to JSON string for unhashable types
            cache_key = f"{prompt_path}:{hash(json.dumps(variables, sort_keys=True))}"
        
        # Check cache with TTL
        if cache_key in self._cache:
            cache_time = self._cache_times.get(cache_key, 0)
            if time.time() - cache_time < self.ttl_seconds:
                return self._cache[cache_key]
        
        # Load template
        try:
            template = self.env.get_template(prompt_path)
        except TemplateNotFound:
            logger.error(f"Prompt template not found: {prompt_path}")
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        
        # Render with variables
        try:
            rendered = template.render(**variables)
        except Exception as e:
            logger.error(f"Error rendering prompt {prompt_path}: {e}")
            raise
        
        # Cache
        self._cache[cache_key] = rendered
        self._cache_times[cache_key] = time.time()
        
        return rendered
    
    def get_examples(self, examples_path: str) -> list[dict]:
        """Load few-shot examples from YAML file.
        
        Args:
            examples_path: Path relative to prompts dir (e.g., "agents/vizql/examples.yaml")
            
        Returns:
            List of example dictionaries with 'user' and 'assistant' keys
            
        Raises:
            FileNotFoundError: If examples file doesn't exist
        """
        full_path = self.prompts_dir / examples_path
        
        if not full_path.exists():
            logger.warning(f"Examples file not found: {examples_path}")
            return []
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'examples' in data:
                    return data['examples']
                else:
                    logger.warning(f"Unexpected format in examples file: {examples_path}")
                    return []
        except Exception as e:
            logger.error(f"Error loading examples from {examples_path}: {e}")
            return []
    
    def build_few_shot_prompt(
        self,
        system_prompt: str,
        examples: list[dict],
        user_query: str
    ) -> list[dict]:
        """Build messages array with few-shot examples.
        
        Args:
            system_prompt: System prompt content
            examples: List of example dicts with 'user' and 'assistant' keys
            user_query: Actual user query to append
            
        Returns:
            List of message dictionaries ready for LLM API
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add examples
        for ex in examples:
            if "user" in ex:
                messages.append({"role": "user", "content": ex["user"]})
            if "assistant" in ex:
                messages.append({"role": "assistant", "content": ex["assistant"]})
        
        # Add actual user query
        messages.append({"role": "user", "content": user_query})
        
        return messages
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()
        self._cache_times.clear()
        logger.info("Prompt cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache size, hit rate, etc.
        """
        return {
            "cache_size": len(self._cache),
            "cached_prompts": list(self._cache.keys())
        }


# Global registry instance
prompt_registry = PromptRegistry()
