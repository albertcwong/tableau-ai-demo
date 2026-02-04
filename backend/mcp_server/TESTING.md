# MCP Server Testing Guide

This guide helps you test the MCP server from both IDE and web interfaces.

## Prerequisites

1. Backend dependencies installed: `pip install -r requirements.txt`
2. Environment variables configured in `.env`
3. Database running and migrations applied
4. FastAPI server can start successfully

## Testing Tools Registration

First, verify that tools are registered correctly:

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python mcp_server/test_tools.py
```

Expected output:
- Server name and version
- List of registered tools (should show 11 tools)
- List of registered resources (should show 3 resources)

## Testing from IDE (Cursor/VS Code)

### Step 1: Verify MCP Configuration

1. Check your `~/.cursor/mcp-config.json` file exists and has correct paths:

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

**Important**: Use absolute paths, not relative paths.

### Step 2: Test Server Startup

Test that the server can start manually:

```bash
cd backend
source venv/bin/activate
python -m mcp_server.server
```

The server should start without errors. Press Ctrl+C to stop it.

### Step 3: Verify Tools in IDE

1. **Restart Cursor/VS Code** after updating MCP config
2. Open the MCP panel (usually in sidebar or via command palette)
3. Look for "tableau-analyst-agent" server
4. Expand to see available tools

**Expected Tools:**
- `tableau_list_datasources`
- `tableau_list_views`
- `tableau_query_datasource`
- `tableau_get_view_embed_url`
- `chat_create_conversation`
- `chat_get_conversation`
- `chat_list_conversations`
- `chat_add_message`
- `chat_get_messages`
- `auth_tableau_signin`
- `auth_get_token`
- `auth_refresh_token`

### Step 4: Test Tool Invocation

1. In the MCP panel, select a tool (e.g., `chat_create_conversation`)
2. Click "Invoke" or use the tool from chat
3. Check the response

**Example**: Test `chat_create_conversation`:
- Should return: `{"conversation_id": <number>, "created_at": "<timestamp>"}`

### Step 5: Test Resource Access

1. In MCP panel, look for resources section
2. Try accessing: `conversation://1` (replace 1 with actual conversation ID)
3. Should return JSON with conversation history

### Troubleshooting IDE Issues

**Problem: Tools not appearing**

1. Check server logs in IDE (look for MCP server output)
2. Verify Python path is correct in config
3. Test server manually: `python -m mcp_server.server`
4. Check for import errors in server logs
5. Verify all dependencies installed: `pip list | grep fastmcp`

**Problem: "spawn python ENOENT" error**

- Use full path to Python executable
- Use `python3` instead of `python` if needed
- Use venv Python: `/path/to/backend/venv/bin/python`

**Problem: Import errors**

- Verify PYTHONPATH includes backend directory
- Check that all dependencies are installed in venv
- Test imports manually: `python -c "from mcp_server.server import mcp"`

## Testing SSE Endpoint (Web)

### Step 1: Start FastAPI Server

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Step 2: Open Test Page

Navigate to: `http://localhost:3000/mcp-test`

Or if frontend is on different port, adjust URL accordingly.

### Step 3: Test Connection

1. Click "Connect" button
2. Should see "Connected" status
3. Should receive "Connected event" immediately
4. Should receive "Heartbeat" events every 30 seconds

### Step 4: Verify Events

Expected events:
- **Connected event**: `{"status": "connected", "server": "tableau-analyst-agent"}`
- **Heartbeat events**: `{"timestamp": <unix_timestamp>}` every 30 seconds

### Step 5: Test Disconnection

1. Click "Disconnect" button
2. Should see "Disconnected" status
3. No more events should arrive

### Troubleshooting SSE Issues

**Problem: Connection fails**

1. Check FastAPI server is running: `curl http://localhost:8000/health`
2. Check SSE endpoint exists: `curl http://localhost:8000/mcp/sse`
3. Check browser console for CORS errors
4. Verify `sse-starlette` is installed: `pip list | grep sse-starlette`

**Problem: No heartbeat events**

1. Check server logs for errors
2. Verify SSE endpoint is working: `curl -N http://localhost:8000/mcp/sse`
3. Check browser network tab for SSE connection

**Problem: CORS errors**

1. Check CORS settings in `app/main.py`
2. Verify frontend URL is in `CORS_ORIGINS` env var
3. Check browser console for specific CORS error

## Manual Testing with curl

### Test SSE Endpoint

```bash
curl -N http://localhost:8000/mcp/sse
```

Should see:
```
event: connected
data: {"status":"connected","server":"tableau-analyst-agent"}

event: heartbeat
data: {"timestamp":1234567890}
...
```

### Test Tool via HTTP (if implemented)

Currently, tools are only available via MCP protocol (stdio/SSE). For HTTP access, you would need to implement additional endpoints in FastAPI.

## Expected Test Results

### ✅ Successful Setup

- Tools appear in IDE MCP panel
- Can invoke tools from IDE
- Resources accessible from IDE
- SSE endpoint connects successfully
- Heartbeat events received every 30 seconds
- No errors in server logs

### ❌ Common Issues

- Tools not appearing → Check MCP config and server startup
- Import errors → Check dependencies and PYTHONPATH
- SSE connection fails → Check FastAPI server and CORS
- No heartbeat → Check server logs for errors

## Next Steps

After successful testing:
1. Integrate MCP tools into your workflows
2. Use tools from IDE chat/composer
3. Build frontend components that use SSE endpoint
4. Implement tool invocation UI in frontend
