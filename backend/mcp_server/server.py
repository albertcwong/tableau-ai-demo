"""MCP Server for Tableau AI Demo."""
import asyncio
import logging
import sys
from fastmcp import FastMCP
from app.core.config import settings

# Configure logging - use stderr for MCP stdio communication
# stdout is used for MCP protocol, so logs go to stderr
logging.basicConfig(
    level=getattr(logging, settings.MCP_LOG_LEVEL.upper() if hasattr(settings, 'MCP_LOG_LEVEL') else 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Important: log to stderr, not stdout
)
logger = logging.getLogger(__name__)

# Create MCP server instance
# FastMCP automatically discovers tools and resources via decorators
mcp = FastMCP(
    name=getattr(settings, 'MCP_SERVER_NAME', 'tableau-analyst-agent'),
    version="1.0.0"
)

# Register mcp instance in package __init__ so tools can access it without circular import
from mcp_server import set_mcp
set_mcp(mcp)

# Ensure mcp is fully initialized before tools import it
# This helps avoid circular import issues
if not hasattr(mcp, '_tool_manager'):
    # Force initialization
    _ = mcp._tool_manager

# Import all tools and resources to register them
# Tools are registered via @mcp.tool() decorators
# Resources are registered via @mcp.resource() decorators
try:
    # Import tools modules individually to catch any import errors
    logger.debug("Importing tableau_tools...")
    try:
        from mcp_server.tools import tableau_tools  # noqa: E402, F401
        # Check if tableau_tools got the same mcp instance
        if hasattr(tableau_tools, 'mcp'):
            tableau_mcp_id = id(tableau_tools.mcp)
            server_mcp_id = id(mcp)
            logger.debug(f"tableau_tools.mcp ID: {tableau_mcp_id}, server.mcp ID: {server_mcp_id}, Same: {tableau_mcp_id == server_mcp_id}")
            if tableau_mcp_id != server_mcp_id:
                logger.warning(f"⚠️  tableau_tools is using different mcp instance! Tools registered on different instance.")
                # Check tools on tableau_tools' mcp instance
                if hasattr(tableau_tools.mcp, '_tool_manager'):
                    tableau_tools_count = len(tableau_tools.mcp._tool_manager._tools) if hasattr(tableau_tools.mcp._tool_manager, '_tools') else 0
                    logger.debug(f"Tools on tableau_tools.mcp: {tableau_tools_count}")
    except Exception as import_error:
        logger.error(f"Failed to import tableau_tools: {import_error}", exc_info=True)
        raise
    
    tool_count_after_tableau = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools') else 0
    logger.debug(f"After tableau_tools import: {tool_count_after_tableau} tools")
    if tool_count_after_tableau == 0:
        logger.warning("⚠️  tableau_tools imported but no tools registered on server.mcp!")
        # Check if tools registered on tableau_tools' mcp instead
        if hasattr(tableau_tools, 'mcp') and hasattr(tableau_tools.mcp, '_tool_manager'):
            alt_count = len(tableau_tools.mcp._tool_manager._tools) if hasattr(tableau_tools.mcp._tool_manager, '_tools') else 0
            if alt_count > 0:
                logger.warning(f"⚠️  But {alt_count} tools found on tableau_tools.mcp instance - instance mismatch!")
    
    logger.debug("Importing chat_tools...")
    from mcp_server.tools import chat_tools  # noqa: E402, F401
    tool_count_after_chat = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools') else 0
    logger.debug(f"After chat_tools import: {tool_count_after_chat} tools")
    
    logger.debug("Importing auth_tools...")
    from mcp_server.tools import auth_tools  # noqa: E402, F401
    tool_count_after_auth = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools') else 0
    logger.debug(f"After auth_tools import: {tool_count_after_auth} tools")
    
    logger.debug("Importing vizql_tools...")
    from mcp_server.tools import vizql_tools  # noqa: E402, F401
    tool_count_after_vizql = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools') else 0
    logger.debug(f"After vizql_tools import: {tool_count_after_vizql} tools")
    
    logger.debug("Importing export_tools...")
    from mcp_server.tools import export_tools  # noqa: E402, F401
    tool_count_after_export = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools') else 0
    logger.debug(f"After export_tools import: {tool_count_after_export} tools")
    
    logger.debug("Importing conversation_resources...")
    from mcp_server.resources import conversation_resources  # noqa: E402, F401
    
    # Force registration by accessing the modules
    # This ensures decorators have executed
    _ = tableau_tools
    _ = chat_tools
    _ = auth_tools
    _ = vizql_tools
    _ = export_tools
    _ = conversation_resources
    
    # Verify tools are registered
    if hasattr(mcp, '_tool_manager'):
        tool_count = len(mcp._tool_manager._tools) if hasattr(mcp._tool_manager, '_tools') else 0
        tool_names = list(mcp._tool_manager._tools.keys()) if hasattr(mcp._tool_manager, '_tools') else []
        logger.info(f"MCP server initialized with {tool_count} tools")
        
        # Log all tool names for debugging
        if tool_count > 0:
            logger.info(f"All tools: {tool_names}")
        else:
            logger.error("⚠️  WARNING: No tools found in tool_manager!")
    else:
        logger.warning("Tool manager not found - tools may not be registered")
    
    # Verify resources are registered
    if hasattr(mcp, '_resource_manager'):
        if hasattr(mcp._resource_manager, '_resources'):
            resource_count = len(mcp._resource_manager._resources)
            logger.info(f"MCP server initialized with {resource_count} resources")
        if hasattr(mcp._resource_manager, '_templates'):
            template_count = len(mcp._resource_manager._templates)
            logger.info(f"MCP server initialized with {template_count} resource templates")
except Exception as e:
    logger.error(f"Failed to import tools/resources: {e}", exc_info=True)
    sys.exit(1)


if __name__ == "__main__":
    # FastMCP handles stdio transport by default when run as main
    # For SSE transport, we'll integrate with FastAPI (see main.py)
    
    # Use the module-level logger, not __main__ logger
    # This ensures consistent logging context
    main_logger = logging.getLogger('mcp_server.server')
    
    # Final verification before starting
    # Check tools using the same mcp instance that was used during imports
    try:
        if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools'):
            final_tool_count = len(mcp._tool_manager._tools)
            final_tool_names = list(mcp._tool_manager._tools.keys())
            
            main_logger.info(f"__main__ check: Found {final_tool_count} tools")
            if final_tool_count > 0:
                main_logger.info(f"Tool names in __main__: {final_tool_names}")
            
            if final_tool_count == 0:
                main_logger.error("⚠️  CRITICAL: No tools registered! Server will not expose any tools.")
                main_logger.error("Check that tool modules imported correctly and decorators executed.")
                # Don't exit - let FastMCP handle it, might be a false negative
                main_logger.warning("Continuing anyway - FastMCP may expose tools differently")
            else:
                main_logger.info(f"✅ Verified {final_tool_count} tools ready for MCP protocol")
        else:
            main_logger.warning("⚠️  Tool manager not accessible - but continuing")
    except Exception as e:
        main_logger.warning(f"Error checking tools: {e} - continuing anyway")
        import traceback
        main_logger.debug(traceback.format_exc())
    
    main_logger.info("Starting MCP server with stdio transport")
    try:
        mcp.run()
    except KeyboardInterrupt:
        main_logger.info("MCP server stopped by user")
    except Exception as e:
        main_logger.error(f"MCP server error: {e}", exc_info=True)
        sys.exit(1)
