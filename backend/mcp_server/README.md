# MCP Server for Tableau AI Demo

This MCP (Model Context Protocol) server exposes Tableau operations, conversation management, and authentication as reusable tools and resources that can be accessed from IDEs (Cursor, VS Code) and web interfaces.

## Features

### Tools

#### Tableau Operations
- `tableau_list_datasources` - List all datasources from Tableau Server
- `tableau_list_views` - List all views with optional filters
- `tableau_query_datasource` - Query a datasource with filters and column selection
- `tableau_get_view_embed_url` - Get embedding URL for a Tableau view

#### Conversation Management
- `chat_create_conversation` - Create a new conversation
- `chat_get_conversation` - Get conversation by ID
- `chat_list_conversations` - List all conversations with pagination
- `chat_add_message` - Add a message to a conversation
- `chat_get_messages` - Get messages for a conversation

#### Authentication
- `auth_tableau_signin` - Authenticate with Tableau Connected Apps (JWT)
- `auth_get_token` - Get current authentication token info
- `auth_refresh_token` - Refresh authentication token

### Resources

- `conversation://{id}` - Access conversation history as a resource
- `datasources://list` - Access cached datasource list
- `views://list` - Access cached view list

## Setup

### Prerequisites

1. Python 3.10+ installed
2. Backend dependencies installed (`pip install -r requirements.txt`)
3. Environment variables configured (see `.env`)

### IDE Integration (Cursor/VS Code)

#### Cursor Configuration

1. Create or edit `~/.cursor/mcp-config.json`:

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/tableau-ai-demo/backend/venv/bin/python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/tableau-ai-demo/backend"
      }
    }
  }
}
```

**Alternative (if python3 is in PATH):**
```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "python3",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/tableau-ai-demo/backend"
      }
    }
  }
}
```

2. Replace `/path/to/tableau-ai-demo/backend` with your actual backend directory path.
   
   **Recommended**: Use the venv Python path (first example) to ensure all dependencies are available.

3. Restart Cursor to load the MCP server.

#### VS Code Configuration

1. Install the MCP extension for VS Code (if available)
2. Add configuration similar to Cursor above
3. Restart VS Code

### Web Integration (SSE)

The MCP server is also accessible via Server-Sent Events (SSE) for web integration:

- **Endpoint**: `GET /mcp/sse`
- **Protocol**: Server-Sent Events
- **Test Page**: `http://localhost:3000/mcp-test` (after starting frontend)
- **Usage**: Connect from frontend using EventSource API

Example frontend connection:

```javascript
const eventSource = new EventSource('/mcp/sse');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('MCP event:', data);
};
```

**Debug Endpoints:**
- `GET /mcp/debug/tools` - List all registered tools
- `GET /mcp/debug/resources` - List all registered resources

## Running the Server

### Standalone (stdio transport)

```bash
cd backend
# Activate virtual environment first
source venv/bin/activate  # On Windows: venv\Scripts\activate
python -m mcp_server.server
```

Or use python3 directly:
```bash
cd backend
python3 -m mcp_server.server
```

### Via FastAPI (SSE transport)

The MCP server is integrated into the FastAPI application. Start the backend:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The SSE endpoint will be available at `http://localhost:8000/mcp/sse`.

## Usage Examples

### List Datasources

```python
# Via MCP tool
result = await tableau_list_datasources(
    project_id="project-123",
    page_size=50
)
```

### Create Conversation

```python
# Via MCP tool
result = await chat_create_conversation()
conversation_id = result["conversation_id"]
```

### Authenticate with Tableau

```python
# Via MCP tool
result = await auth_tableau_signin(
    server_url="https://tableau.example.com",
    client_id="your-client-id",
    client_secret="your-client-secret",
    username="tableau-user"
)
```

### Access Conversation Resource

```
conversation://123
```

Returns JSON with conversation history.

## Security

- **Credential Storage**: Authentication credentials are stored encrypted using Fernet encryption
- **Token Management**: Tokens are cached securely and refreshed automatically
- **Environment Variables**: Sensitive configuration should be in `.env` file (gitignored)

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing guide including:
- Testing tool registration
- Testing from IDE (Cursor/VS Code)
- Testing SSE endpoint
- Troubleshooting common issues

Quick test commands:
```bash
# Test tool registration
python mcp_server/test_tools.py

# Test SSE endpoint (after starting FastAPI)
curl -N http://localhost:8000/mcp/sse

# Check registered tools
curl http://localhost:8000/mcp/debug/tools

# Check registered resources
curl http://localhost:8000/mcp/debug/resources
```

## Troubleshooting

### Server won't start

1. Check Python version: `python3 --version` (must be 3.10+)
2. Verify dependencies: `pip list | grep fastmcp`
3. Check environment variables: Ensure `.env` is configured

### "spawn python ENOENT" error

This error means the `python` command is not found. Solutions:

1. **Use python3 instead**: Change `"command": "python"` to `"command": "python3"` in your MCP config
2. **Use venv Python (recommended)**: Use the full path to your venv's Python:
   ```json
   "command": "/path/to/backend/venv/bin/python"
   ```
3. **Check PATH**: Ensure Python is in your system PATH, or use the full path

### Tools not appearing in IDE

### Tools not appearing in IDE

1. Verify MCP config file location and syntax
2. Check server logs for errors
3. Restart IDE after configuration changes

### Authentication failures

1. Verify Tableau credentials in `.env`
2. Check Tableau server URL and SSL certificate configuration
3. Ensure Connected App is properly configured in Tableau

## Development

### Adding New Tools

1. Create tool function in appropriate module (`tools/tableau_tools.py`, etc.)
2. Decorate with `@mcp.tool()`
3. Add docstring with parameter descriptions
4. Import module in `server.py` to register

### Adding New Resources

1. Create resource function in `resources/conversation_resources.py`
2. Decorate with `@mcp.resource("uri://pattern")`
3. Import module in `server.py` to register

## Architecture

The MCP server uses FastMCP framework which:
- Automatically discovers tools and resources via decorators
- Handles MCP protocol communication
- Supports both stdio (IDE) and SSE (web) transports
- Provides type-safe tool definitions

## License

See main project LICENSE file.
