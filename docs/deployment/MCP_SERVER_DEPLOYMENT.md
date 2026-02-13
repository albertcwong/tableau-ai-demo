# MCP Server Deployment Guide

This guide covers deploying the MCP (Model Context Protocol) server in different environments.

## Overview

The MCP server can be deployed in two transport modes:

1. **stdio**: For IDE integration (Cursor, VS Code)
2. **SSE**: For web integration (Server-Sent Events)

## Transport Modes

### stdio Transport (IDE Integration)

**Use Case**: Direct integration with IDEs like Cursor or VS Code

**How it works**:
- IDE spawns MCP server as subprocess
- Communication via stdin/stdout
- No network port required
- One server instance per IDE connection

**Deployment**:
- Not deployed as a service
- Runs on-demand when IDE connects
- Configured via IDE's MCP config file

### SSE Transport (Web Integration)

**Use Case**: Web frontend integration via HTTP

**How it works**:
- MCP server runs as HTTP service
- Exposes SSE endpoint at `/mcp/sse`
- Frontend connects via EventSource API
- Supports multiple concurrent connections

**Deployment**:
- Deployed as Docker container
- Exposes port 8002
- Integrated with FastAPI backend

## Docker Deployment (SSE Mode)

### Using Docker Compose

**Note**: MCP SSE endpoints are integrated into the FastAPI backend service. The backend service exposes MCP endpoints at `/mcp/sse` and `/mcp/debug/*`.

Access MCP SSE via backend:
```bash
curl http://localhost:8000/mcp/sse
curl http://localhost:8000/mcp/debug/tools
```

The backend service already includes MCP functionality - no separate MCP server service needed for SSE transport.

For stdio mode (IDE integration), the MCP server runs on-demand when IDEs connect (not as a Docker service).

### Standalone Docker

Build image:
```bash
docker build -t tableau-mcp-server -f backend/Dockerfile.mcp backend/
```

Run container:
```bash
docker run -d \
  --name mcp-server \
  -p 8002:8002 \
  -e MCP_TRANSPORT=sse \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e GATEWAY_BASE_URL=http://backend:8000/api/v1/gateway \
  -v ./credentials:/app/credentials:ro \
  tableau-mcp-server
```

## IDE Integration (stdio Mode)

### Cursor Configuration

1. Create/edit `~/.cursor/mcp-config.json`:

```json
{
  "mcpServers": {
    "tableau-analyst-agent": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/tableau_demo",
        "GATEWAY_BASE_URL": "http://localhost:8000/api/v1/gateway",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

2. Restart Cursor

3. Verify connection in MCP panel

### VS Code Configuration

1. Install MCP extension (if available)

2. Configure in VS Code settings:

```json
{
  "mcp.servers": {
    "tableau-analyst-agent": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "/path/to/backend",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/tableau_demo",
        "GATEWAY_BASE_URL": "http://localhost:8000/api/v1/gateway"
      }
    }
  }
}
```

## Environment Variables

### Required

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
GATEWAY_BASE_URL=http://backend:8000/api/v1/gateway
```

### Optional

```bash
MCP_TRANSPORT=sse  # or stdio (default)
MCP_SERVER_NAME=tableau-analyst-agent
MCP_LOG_LEVEL=info  # debug, info, warning, error

# Tableau credentials (if using Tableau tools)
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_SITE_ID=your-site-id
TABLEAU_CLIENT_ID=your-client-id
TABLEAU_CLIENT_SECRET=your-client-secret
```

## Health Checks

### SSE Mode

Check health endpoint:
```bash
curl http://localhost:8002/mcp/debug/tools
```

Expected response:
```json
{
  "server_name": "tableau-analyst-agent",
  "server_version": "1.0.0",
  "tools_count": 11,
  "tools": [...]
}
```

### stdio Mode

Health checks not applicable (runs on-demand)

## Testing Deployment

### Test SSE Endpoint

1. Connect to SSE endpoint:
```bash
curl -N http://localhost:8002/mcp/sse
```

2. Should receive:
```
event: connected
data: {"status":"connected","server":"tableau-analyst-agent"}

event: heartbeat
data: {"timestamp":1234567890}
```

### Test Tool Invocation (SSE)

Use the frontend test page:
```
http://localhost:3000/mcp-test
```

Or use curl with SSE client library.

### Test Tool Invocation (stdio)

From IDE:
1. Open MCP panel
2. Select `tableau-analyst-agent`
3. Invoke tool (e.g., `chat_create_conversation`)
4. Verify response

## Troubleshooting

### SSE Mode Issues

**Problem**: Connection refused
- Check port 8002 is exposed
- Verify container is running: `docker-compose ps mcp-server`
- Check logs: `docker-compose logs mcp-server`

**Problem**: Tools not appearing
- Check `/mcp/debug/tools` endpoint
- Verify database connection
- Check MCP_LOG_LEVEL=debug for detailed logs

**Problem**: CORS errors
- Ensure CORS is configured in FastAPI backend
- Check frontend is connecting to correct URL

### stdio Mode Issues

**Problem**: Server won't start
- Verify Python path is correct
- Check PYTHONPATH includes backend directory
- Test manually: `python -m mcp_server.server`

**Problem**: Tools not appearing in IDE
- Check MCP config file syntax
- Verify environment variables are set
- Check IDE logs for errors
- See [TROUBLESHOOTING.md](./backend/mcp_server/TROUBLESHOOTING.md)

**Problem**: Import errors
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Verify PYTHONPATH is correct
- Check `python -c "from mcp_server.server import mcp"` works

## Production Considerations

### Security

1. **Network isolation**
   - Don't expose MCP server port publicly (SSE mode)
   - Use reverse proxy with authentication
   - Restrict access to internal network only

2. **Credentials**
   - Store credentials securely (Docker secrets, vault)
   - Never commit credentials to repository
   - Use read-only mounts for credential files

3. **Rate limiting**
   - Implement rate limiting on SSE endpoint
   - Monitor for abuse
   - Set connection limits

### Performance

1. **Connection pooling**
   - Database connection pooling configured
   - Redis connection pooling configured
   - Gateway connection reuse

2. **Caching**
   - Resource caching enabled (5min TTL)
   - Token caching in Redis
   - Consider CDN for static resources

3. **Scaling**
   - SSE mode: Scale horizontally behind load balancer
   - stdio mode: One instance per IDE connection (automatic)

### Monitoring

1. **Logs**
   - Centralized logging (ELK, Loki)
   - Log aggregation for distributed deployment
   - Set appropriate log levels

2. **Metrics**
   - Track tool invocation counts
   - Monitor response times
   - Alert on errors

3. **Health checks**
   - Use `/mcp/debug/tools` for health checks
   - Monitor database connectivity
   - Check gateway availability

## Migration Between Modes

### From stdio to SSE

1. Update environment: `MCP_TRANSPORT=sse`
2. Deploy as Docker service
3. Update frontend to use SSE endpoint
4. Test connectivity

### From SSE to stdio

1. Stop Docker service
2. Configure IDE MCP config
3. Test IDE integration
4. Update documentation

## Support

For issues:
- Check logs: `docker-compose logs mcp-server`
- Review [TROUBLESHOOTING.md](./backend/mcp_server/TROUBLESHOOTING.md)
- Test tools: `python mcp_server/test_tools.py`
- Open GitHub issue
