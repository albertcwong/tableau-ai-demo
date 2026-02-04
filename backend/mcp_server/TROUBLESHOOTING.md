# MCP Server Troubleshooting Guide

## Issue: Cursor Shows 0 Tools, Prompts, and Resources

### Symptoms
- MCP server appears in Cursor's MCP panel
- Server shows as connected
- But displays "0 tools, 0 prompts, 0 resources"
- Server logs show "Processing request of type ListToolsRequest" but returns 0 tools
- Tools ARE registered (verified with test_tools.py showing 12 tools)

### Known Issue
This appears to be a **known bug in FastMCP 2.14.4** where tools are registered correctly but not exposed via the MCP protocol handler. The tools exist in `_tool_manager._tools` but `_list_tools_mcp` returns empty.

**Solution: Try upgrading FastMCP**
```bash
cd backend
source venv/bin/activate
pip install --upgrade fastmcp
```

Then restart Cursor and test again. If the issue persists, check FastMCP GitHub issues for updates.

### Diagnosis Steps

1. **Verify Tools Are Registered Locally**

   Run the test script:
   ```bash
   cd backend
   source venv/bin/activate
   python mcp_server/test_tools.py
   ```
   
   Expected output: Should show 12 tools and 3 resources

2. **Check for Import Errors**

   Run the import check:
   ```bash
   python mcp_server/check_imports.py
   ```
   
   All imports should succeed.

3. **Test Server Startup**

   Try starting the server manually:
   ```bash
   python -m mcp_server.server
   ```
   
   The server should start without errors. Press Ctrl+C to stop.

4. **Check Cursor Logs**

   Look for MCP server logs in Cursor:
   - Open Cursor's developer console
   - Look for MCP-related errors
   - Check for import errors or initialization failures

5. **Verify MCP Config**

   Check `~/.cursor/mcp-config.json`:
   ```json
   {
     "mcpServers": {
       "tableau-analyst-agent": {
         "command": "/full/path/to/backend/venv/bin/python",
         "args": ["-m", "mcp_server.server"],
         "env": {
           "PYTHONPATH": "/full/path/to/backend"
         }
       }
     }
   }
   ```
   
   **Important:**
   - Use absolute paths, not relative
   - Use the venv Python, not system Python
   - PYTHONPATH must include the backend directory

6. **Check Environment Variables**

   The server needs access to `.env` file. Verify:
   - `.env` file exists in project root
   - Contains required variables (at minimum DATABASE_URL)
   - Server can read the file

### Common Issues and Solutions

#### Issue: Server Starts But Shows 0 Tools

**Possible Causes:**
1. Import errors are silently failing
2. Tools aren't being registered before server starts
3. MCP protocol handshake failing

**Solution:**
- Check server logs (should go to stderr)
- Verify all imports succeed
- Ensure tools are imported before `mcp.run()` is called

#### Issue: "spawn python ENOENT"

**Solution:**
- Use full path to Python executable
- Use venv Python: `/path/to/backend/venv/bin/python`
- Or use `python3` if in PATH

#### Issue: Import Errors

**Solution:**
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check PYTHONPATH includes backend directory
- Test imports manually: `python -c "from mcp_server.server import mcp"`

#### Issue: Tools Registered But Not Visible in Cursor

**Possible Causes:**
1. Cursor cache issue
2. MCP protocol version mismatch
3. Server not responding to list_tools request

**Solution:**
1. Restart Cursor completely
2. Clear Cursor's MCP cache (if exists)
3. Check Cursor logs for protocol errors
4. Verify FastMCP version compatibility

### Debug Mode

Enable debug logging by setting in `.env`:
```
MCP_LOG_LEVEL=DEBUG
```

Then restart the server and check logs.

### Manual Protocol Test

You can test the MCP protocol manually using `mcp-cli` or similar tools:

```bash
# Install mcp-cli if available
pip install mcp-cli

# Test server
mcp-cli test --command "python -m mcp_server.server"
```

### Getting Help

If issues persist:
1. Collect logs from Cursor's developer console
2. Run `python mcp_server/test_tools.py` and share output
3. Run `python mcp_server/check_imports.py` and share output
4. Check FastMCP version: `pip show fastmcp`
5. Verify Python version: `python --version` (should be 3.10+)

### Expected Behavior

When working correctly:
- Server starts without errors
- Cursor shows "12 tools, 0 prompts, 3 resources"
- Tools are callable from Cursor
- Resources are accessible
