"""MCP Server package - exports mcp instance for tools to use."""
# This file allows tools to import mcp without circular import issues
# The mcp instance will be set by server.py after it's created

_mcp_instance = None

def get_mcp():
    """Get the MCP server instance."""
    global _mcp_instance
    if _mcp_instance is None:
        # Import from server - this will work because server.py sets _mcp_instance
        from mcp_server.server import mcp
        _mcp_instance = mcp
    return _mcp_instance

def set_mcp(instance):
    """Set the MCP server instance (called by server.py)."""
    global _mcp_instance
    _mcp_instance = instance

def get_auth0_token():
    """Get Auth0 access token (if available)."""
    from mcp_server.server import get_auth0_token as _get_token
    return _get_token()

def get_auth0_user_id():
    """Get Auth0 user ID (sub claim) from validated token."""
    from mcp_server.server import get_auth0_user_id as _get_user_id
    return _get_user_id()
