"""Unit tests for PromptRegistry."""
import pytest
import tempfile
import shutil
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.prompts.registry import PromptRegistry


@pytest.fixture
def temp_prompts_dir():
    """Create temporary prompts directory for testing."""
    temp_dir = tempfile.mkdtemp()
    prompts_dir = Path(temp_dir) / "prompts"
    prompts_dir.mkdir()
    
    # Create test prompt file
    test_prompt = prompts_dir / "test.txt"
    test_prompt.write_text("Hello {{ name }}!")
    
    # Create test examples file
    examples_dir = prompts_dir / "agents" / "test"
    examples_dir.mkdir(parents=True)
    examples_file = examples_dir / "examples.yaml"
    examples_file.write_text("""
examples:
  - user: "test query"
    assistant: "test response"
""")
    
    yield prompts_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


def test_prompt_registry_init(temp_prompts_dir):
    """Test PromptRegistry initialization."""
    registry = PromptRegistry(temp_prompts_dir)
    assert registry.prompts_dir == temp_prompts_dir
    assert len(registry._cache) == 0


def test_get_prompt_without_variables(temp_prompts_dir):
    """Test loading prompt without variables."""
    registry = PromptRegistry(temp_prompts_dir)
    
    # Create a simple prompt file
    simple_prompt = temp_prompts_dir / "simple.txt"
    simple_prompt.write_text("Hello World")
    
    result = registry.get_prompt("simple.txt")
    assert result == "Hello World"


def test_get_prompt_with_variables(temp_prompts_dir):
    """Test loading prompt with variable substitution."""
    registry = PromptRegistry(temp_prompts_dir)
    
    result = registry.get_prompt("test.txt", variables={"name": "Alice"})
    assert result == "Hello Alice!"


def test_get_prompt_caching(temp_prompts_dir):
    """Test prompt caching."""
    registry = PromptRegistry(temp_prompts_dir)
    
    # First call
    result1 = registry.get_prompt("test.txt", variables={"name": "Bob"})
    
    # Second call should use cache
    result2 = registry.get_prompt("test.txt", variables={"name": "Bob"})
    
    assert result1 == result2
    assert len(registry._cache) == 1


def test_get_prompt_different_variables(temp_prompts_dir):
    """Test that different variables create different cache entries."""
    registry = PromptRegistry(temp_prompts_dir)
    
    result1 = registry.get_prompt("test.txt", variables={"name": "Alice"})
    result2 = registry.get_prompt("test.txt", variables={"name": "Bob"})
    
    assert result1 != result2
    assert len(registry._cache) == 2


def test_get_prompt_not_found(temp_prompts_dir):
    """Test error handling for missing prompt."""
    registry = PromptRegistry(temp_prompts_dir)
    
    with pytest.raises(FileNotFoundError):
        registry.get_prompt("nonexistent.txt")


def test_get_examples(temp_prompts_dir):
    """Test loading examples from YAML."""
    registry = PromptRegistry(temp_prompts_dir)
    
    examples = registry.get_examples("agents/test/examples.yaml")
    
    assert len(examples) == 1
    assert examples[0]["user"] == "test query"
    assert examples[0]["assistant"] == "test response"


def test_get_examples_not_found(temp_prompts_dir):
    """Test handling missing examples file."""
    registry = PromptRegistry(temp_prompts_dir)
    
    examples = registry.get_examples("nonexistent.yaml")
    assert examples == []


def test_build_few_shot_prompt(temp_prompts_dir):
    """Test building few-shot prompt messages."""
    registry = PromptRegistry(temp_prompts_dir)
    
    examples = [
        {"user": "query 1", "assistant": "response 1"},
        {"user": "query 2", "assistant": "response 2"}
    ]
    
    messages = registry.build_few_shot_prompt(
        "System prompt",
        examples,
        "Actual user query"
    )
    
    assert len(messages) == 6  # system + 2 examples (user+assistant each) + user query
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "System prompt"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "query 1"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "response 1"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Actual user query"


def test_clear_cache(temp_prompts_dir):
    """Test cache clearing."""
    registry = PromptRegistry(temp_prompts_dir)
    
    # Load some prompts to populate cache
    registry.get_prompt("test.txt", variables={"name": "Alice"})
    assert len(registry._cache) > 0
    
    # Clear cache
    registry.clear_cache()
    assert len(registry._cache) == 0


def test_get_cache_stats(temp_prompts_dir):
    """Test cache statistics."""
    registry = PromptRegistry(temp_prompts_dir)
    
    registry.get_prompt("test.txt", variables={"name": "Alice"})
    
    stats = registry.get_cache_stats()
    assert stats["cache_size"] == 1
    assert len(stats["cached_prompts"]) == 1
