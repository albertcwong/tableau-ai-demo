#!/usr/bin/env python3
"""Quick verification script for Sprint 2 implementation."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...")
    
    try:
        # Test node imports
        from app.services.agents.vizql.nodes.planner import plan_query_node
        print("  ✓ planner node imported")
        
        from app.services.agents.vizql.nodes.schema_fetch import fetch_schema_node
        print("  ✓ schema_fetch node imported")
        
        from app.services.agents.vizql.nodes.query_builder import build_query_node
        print("  ✓ query_builder node imported")
        
        from app.services.agents.vizql.nodes.validator import validate_query_node
        print("  ✓ validator node imported")
        
        from app.services.agents.vizql.nodes.refiner import refine_query_node
        print("  ✓ refiner node imported")
        
        from app.services.agents.vizql.nodes.executor import execute_query_node
        print("  ✓ executor node imported")
        
        from app.services.agents.vizql.nodes.formatter import format_results_node
        print("  ✓ formatter node imported")
        
        # Test graph import
        from app.services.agents.vizql.graph import create_vizql_graph
        print("  ✓ graph module imported")
        
        # Test graph factory
        from app.services.agents.graph_factory import AgentGraphFactory
        print("  ✓ graph factory imported")
        
        print("\n✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_creation():
    """Test that graph can be created."""
    print("\nTesting graph creation...")
    
    try:
        from app.services.agents.graph_factory import AgentGraphFactory
        
        graph = AgentGraphFactory.create_vizql_graph()
        print("  ✓ VizQL graph created successfully")
        
        # Check that graph has expected structure
        if hasattr(graph, "nodes"):
            print(f"  ✓ Graph has {len(graph.nodes)} nodes")
        
        print("\n✅ Graph creation successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Graph creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tableau_client_method():
    """Test that execute_vds_query method exists."""
    print("\nTesting TableauClient.execute_vds_query...")
    
    try:
        from app.services.tableau.client import TableauClient
        
        # Check method exists
        assert hasattr(TableauClient, 'execute_vds_query')
        print("  ✓ execute_vds_query method exists")
        
        # Check signature
        import inspect
        sig = inspect.signature(TableauClient.execute_vds_query)
        params = list(sig.parameters.keys())
        assert 'query_obj' in params
        print(f"  ✓ Method signature correct: {params}")
        
        print("\n✅ TableauClient method check successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ TableauClient check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Sprint 2 Verification")
    print("=" * 60)
    
    results = []
    results.append(test_imports())
    results.append(test_graph_creation())
    results.append(test_tableau_client_method())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All Sprint 2 components verified successfully!")
        print("\nNext steps:")
        print("1. Run unit tests: pytest tests/unit/agents/vizql/test_nodes.py -v")
        print("2. Create integration tests for full graph execution")
        print("3. Test with real Tableau datasource (requires credentials)")
        return 0
    else:
        print("❌ Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
