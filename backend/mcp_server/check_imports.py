"""Check for import errors in MCP server modules."""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

print("=" * 80)
print("MCP Server Import Check")
print("=" * 80)

errors = []

try:
    print("\n1. Importing FastMCP...")
    from fastmcp import FastMCP
    print("   ✅ FastMCP imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("FastMCP", e))

try:
    print("\n2. Importing app.core.config...")
    from app.core.config import settings
    print("   ✅ Config imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("Config", e))

try:
    print("\n3. Importing mcp_server.server...")
    from mcp_server.server import mcp
    print("   ✅ MCP server imported successfully")
    print(f"   Server name: {mcp.name}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("MCP Server", e))
    import traceback
    traceback.print_exc()

try:
    print("\n4. Importing tableau_tools...")
    from mcp_server.tools import tableau_tools
    print("   ✅ Tableau tools imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("Tableau Tools", e))
    import traceback
    traceback.print_exc()

try:
    print("\n5. Importing chat_tools...")
    from mcp_server.tools import chat_tools
    print("   ✅ Chat tools imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("Chat Tools", e))
    import traceback
    traceback.print_exc()

try:
    print("\n6. Importing auth_tools...")
    from mcp_server.tools import auth_tools
    print("   ✅ Auth tools imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("Auth Tools", e))
    import traceback
    traceback.print_exc()

try:
    print("\n7. Importing conversation_resources...")
    from mcp_server.resources import conversation_resources
    print("   ✅ Conversation resources imported successfully")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    errors.append(("Resources", e))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
if errors:
    print(f"❌ Found {len(errors)} import errors:")
    for module, error in errors:
        print(f"  - {module}: {error}")
else:
    print("✅ All imports successful!")
print("=" * 80)
