"""Test script to verify MCP tools are registered correctly."""
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from mcp_server.server import mcp


async def test_tools():
    """Test that tools are registered."""
    print("=" * 80)
    print("MCP Server Tool Registration Test")
    print("=" * 80)
    print(f"\nServer Name: {mcp.name}")
    print(f"Server Version: {mcp.version}")
    
    # Get registered tools - check tool_manager directly (synchronous access)
    try:
        if hasattr(mcp, '_tool_manager'):
            tool_manager = mcp._tool_manager
            if hasattr(tool_manager, '_tools'):
                tools_dict = tool_manager._tools
                print(f"\n✅ Found {len(tools_dict)} registered tools:")
                for name, tool in tools_dict.items():
                    print(f"  - {name}")
                    if hasattr(tool, 'description') and tool.description:
                        desc = tool.description[:80] if len(tool.description) > 80 else tool.description
                        print(f"    {desc}")
        else:
            print("\n⚠️  Could not find _tool_manager")
    except Exception as e:
        print(f"\n❌ Error accessing tools: {e}")
        import traceback
        traceback.print_exc()
    
    # Get registered resources - check resource_manager directly
    try:
        if hasattr(mcp, '_resource_manager'):
            resource_manager = mcp._resource_manager
            if hasattr(resource_manager, '_resources'):
                resources_dict = resource_manager._resources
                print(f"\n✅ Found {len(resources_dict)} registered resources:")
                for uri in resources_dict.keys():
                    print(f"  - {uri}")
            
            # Also check resource templates
            if hasattr(resource_manager, '_templates'):
                templates_dict = resource_manager._templates
                print(f"\n✅ Found {len(templates_dict)} resource templates:")
                for uri_template in templates_dict.keys():
                    print(f"  - {uri_template}")
        else:
            print("\n⚠️  Could not find _resource_manager")
    except Exception as e:
        print(f"\n❌ Error accessing resources: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tools())
