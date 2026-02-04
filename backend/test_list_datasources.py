"""Quick test script to list datasources."""
import asyncio
import sys
from app.services.ai.tools import list_datasources_tool
from app.services.ai.agent import Agent, Intent

async def test_list_datasources():
    """Test listing datasources."""
    print("Testing list_datasources_tool...")
    try:
        result = await list_datasources_tool()
        print(f"\n✓ Success! Found {len(result)} datasource(s):\n")
        for ds in result:
            print(f"  - {ds.get('name', 'Unknown')} (ID: {ds.get('id', 'N/A')})")
            if ds.get('project_name'):
                print(f"    Project: {ds.get('project_name')}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_intent_classification():
    """Test intent classification."""
    print("\nTesting intent classification...")
    agent = Agent()
    query = "list all datasources"
    intent = agent.classify_intent(query)
    print(f"Query: '{query}'")
    print(f"Intent: {intent.value}")
    
    plan = agent.create_plan(query, intent)
    print(f"\nPlan:")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step['description']}")

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 7: Agentic Capabilities Test")
    print("=" * 60)
    
    # Test intent classification first (doesn't require Tableau connection)
    asyncio.run(test_intent_classification())
    
    # Test actual tool execution (requires Tableau connection)
    print("\n" + "=" * 60)
    asyncio.run(test_list_datasources())
