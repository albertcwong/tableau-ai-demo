#!/usr/bin/env python3
"""Quick verification script for Sprint 3 implementation."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...")
    
    try:
        # Test node imports
        from app.services.agents.summary.nodes.data_fetcher import fetch_data_node
        print("  ✓ data_fetcher node imported")
        
        from app.services.agents.summary.nodes.analyzer import analyze_data_node
        print("  ✓ analyzer node imported")
        
        from app.services.agents.summary.nodes.insight_gen import generate_insights_node
        print("  ✓ insight_gen node imported")
        
        from app.services.agents.summary.nodes.summarizer import summarize_node
        print("  ✓ summarizer node imported")
        
        # Test graph import
        from app.services.agents.summary.graph import create_summary_graph
        print("  ✓ graph module imported")
        
        # Test graph factory
        from app.services.agents.graph_factory import AgentGraphFactory
        print("  ✓ graph factory imported")
        
        # Test TableauClient methods
        from app.services.tableau.client import TableauClient
        assert hasattr(TableauClient, 'get_view_data')
        assert hasattr(TableauClient, 'get_view')
        print("  ✓ TableauClient methods exist")
        
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
        
        graph = AgentGraphFactory.create_summary_graph()
        print("  ✓ Summary graph created successfully")
        
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


def test_statistical_libraries():
    """Test that pandas and numpy are available."""
    print("\nTesting statistical libraries...")
    
    try:
        import pandas as pd
        import numpy as np
        print(f"  ✓ pandas {pd.__version__} imported")
        print(f"  ✓ numpy {np.__version__} imported")
        
        # Quick test
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert len(df) == 3
        print("  ✓ Basic pandas operations work")
        
        arr = np.array([1, 2, 3])
        assert len(arr) == 3
        print("  ✓ Basic numpy operations work")
        
        print("\n✅ Statistical libraries working!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Library import failed: {e}")
        print("  Install with: pip3 install pandas numpy")
        return False
    except Exception as e:
        print(f"\n❌ Library test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Sprint 3 Verification")
    print("=" * 60)
    
    results = []
    results.append(test_imports())
    results.append(test_graph_creation())
    results.append(test_statistical_libraries())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All Sprint 3 components verified successfully!")
        print("\nNext steps:")
        print("1. Install dependencies: pip3 install pandas numpy")
        print("2. Run unit tests: pytest tests/unit/agents/summary/ -v")
        print("3. Create integration tests for full graph execution")
        print("4. Test with real Tableau view (requires credentials)")
        return 0
    else:
        print("❌ Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
