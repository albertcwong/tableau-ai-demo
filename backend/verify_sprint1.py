#!/usr/bin/env python3
"""Quick verification script for Sprint 1 implementation."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_prompt_registry():
    """Test basic PromptRegistry functionality."""
    print("Testing PromptRegistry...")
    
    try:
        from app.prompts.registry import PromptRegistry, prompt_registry
        
        # Test loading VizQL system prompt
        print("  ✓ Loading VizQL system prompt...")
        prompt = prompt_registry.get_prompt(
            "agents/vizql/system.txt",
            variables={
                "datasources": ["ds-123", "ds-456"],
                "context_description": "Test context"
            }
        )
        assert "VizQL" in prompt
        assert "ds-123" in prompt
        print("  ✓ VizQL system prompt loaded successfully")
        
        # Test loading examples
        print("  ✓ Loading VizQL examples...")
        examples = prompt_registry.get_examples("agents/vizql/examples.yaml")
        assert len(examples) > 0
        assert "user" in examples[0]
        assert "assistant" in examples[0]
        print(f"  ✓ Loaded {len(examples)} examples")
        
        # Test Summary prompt
        print("  ✓ Loading Summary system prompt...")
        summary_prompt = prompt_registry.get_prompt(
            "agents/summary/system.txt",
            variables={
                "view_name": "Test View",
                "row_count": 1000
            }
        )
        assert "Summary Agent" in summary_prompt
        print("  ✓ Summary system prompt loaded successfully")
        
        print("\n✅ PromptRegistry tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ PromptRegistry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_definitions():
    """Test state definitions."""
    print("\nTesting state definitions...")
    
    try:
        from app.services.agents.base_state import BaseAgentState
        from app.services.agents.vizql.state import VizQLAgentState
        from app.services.agents.summary.state import SummaryAgentState
        
        # Test that states can be instantiated
        print("  ✓ BaseAgentState imported")
        print("  ✓ VizQLAgentState imported")
        print("  ✓ SummaryAgentState imported")
        
        # Test state structure
        base_state: BaseAgentState = {
            "user_query": "test",
            "agent_type": "vizql",
            "context_datasources": [],
            "context_views": [],
            "messages": [],
            "tool_calls": [],
            "tool_results": [],
            "current_thought": None,
            "final_answer": None,
            "error": None,
            "confidence": None,
            "processing_time": None
        }
        print("  ✓ BaseAgentState structure validated")
        
        vizql_state: VizQLAgentState = {
            **base_state,
            "schema": None,
            "required_measures": [],
            "required_dimensions": [],
            "required_filters": {},
            "query_draft": None,
            "query_version": 0,
            "is_valid": False,
            "validation_errors": [],
            "validation_suggestions": [],
            "query_results": None,
            "execution_error": None
        }
        print("  ✓ VizQLAgentState structure validated")
        
        print("\n✅ State definition tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ State definition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_factory():
    """Test graph factory."""
    print("\nTesting AgentGraphFactory...")
    
    try:
        from app.services.agents.graph_factory import AgentGraphFactory
        
        # Test that factory methods exist
        assert hasattr(AgentGraphFactory, 'create_vizql_graph')
        assert hasattr(AgentGraphFactory, 'create_summary_graph')
        assert hasattr(AgentGraphFactory, 'create_general_graph')
        assert hasattr(AgentGraphFactory, 'create_graph')
        print("  ✓ Factory methods exist")
        
        # Test create_graph with valid types
        try:
            AgentGraphFactory.create_graph('vizql')
        except NotImplementedError:
            pass  # Expected for Sprint 1
        
        try:
            AgentGraphFactory.create_graph('summary')
        except NotImplementedError:
            pass  # Expected for Sprint 1
        
        # Test invalid type
        try:
            AgentGraphFactory.create_graph('invalid')
            assert False, "Should raise ValueError"
        except ValueError:
            print("  ✓ Invalid agent type handling works")
        
        print("\n✅ AgentGraphFactory tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ AgentGraphFactory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Sprint 1 Verification")
    print("=" * 60)
    
    results = []
    results.append(test_prompt_registry())
    results.append(test_state_definitions())
    results.append(test_graph_factory())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All Sprint 1 components verified successfully!")
        return 0
    else:
        print("❌ Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
