"""Debug script to test FastMCP tool exposure via MCP protocol."""
import sys
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from mcp_server.server import mcp

# Simulate what FastMCP's _list_tools_mcp does
print("=" * 80)
print("Debugging FastMCP Tool Exposure")
print("=" * 80)

# Check tool_manager
if hasattr(mcp, '_tool_manager'):
    print(f"\n✅ Tool manager exists")
    tool_manager = mcp._tool_manager
    
    if hasattr(tool_manager, '_tools'):
        tools = tool_manager._tools
        print(f"✅ Found {len(tools)} tools in _tool_manager._tools")
        print(f"   Tool names: {list(tools.keys())[:5]}...")
        
        # Check if tools have the right structure
        if tools:
            first_tool_name = list(tools.keys())[0]
            first_tool = tools[first_tool_name]
            print(f"\n📋 First tool structure:")
            print(f"   Name: {first_tool_name}")
            print(f"   Type: {type(first_tool)}")
            print(f"   Attributes: {[a for a in dir(first_tool) if not a.startswith('__')][:10]}")
    else:
        print("❌ No _tools attribute in tool_manager")
else:
    print("❌ No _tool_manager attribute")

# Try to call FastMCP's internal list_tools method
print("\n" + "=" * 80)
print("Testing FastMCP's list_tools method")
print("=" * 80)

try:
    # Check if there's a way to see what FastMCP would return
    if hasattr(mcp, '_list_tools_mcp'):
        print("✅ _list_tools_mcp method exists")
    else:
        print("⚠️  _list_tools_mcp method not found")
        
    if hasattr(mcp, '_mcp_server'):
        print(f"✅ _mcp_server exists: {type(mcp._mcp_server)}")
    else:
        print("⚠️  _mcp_server not found")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
