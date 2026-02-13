# Architecture Documentation

This document describes the architecture of the Tableau AI Demo application, including how services communicate and their primary responsibilities.

## Overview

The application consists of four main services plus supporting infrastructure:

1. **Frontend** (Next.js) - User interface
2. **Backend** (FastAPI) - Main API server
3. **Gateway** (Unified LLM Gateway) - LLM provider abstraction
4. **MCP Server** - Model Context Protocol server
5. **PostgreSQL** - Database
6. **Redis** - Token caching

## Service Communication Flow

```
┌─────────────┐
│   Frontend  │ (Next.js - Port 3000)
│  (Browser)  │
└──────┬──────┘
       │ HTTPS/REST API
       │ SSE (Server-Sent Events)
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                        │
│                    Port 8000                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ • Chat API (/api/v1/chat/*)                         │  │
│  │ • Tableau API (/api/v1/tableau/*)                  │  │
│  │ • Gateway Proxy (/api/v1/gateway/*)                │  │
│  │ • MCP SSE Endpoint (/mcp/sse)                       │  │
│  └──────────────────────────────────────────────────────┘  │
└──────┬──────────────────┬──────────────────┬──────────────┘
       │                  │                  │
       │ HTTP             │ HTTP             │ Internal
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  PostgreSQL  │   │    Redis     │   │   Gateway    │
│  Port 5432   │   │  Port 6379   │   │ (Integrated) │
└──────────────┘   └──────────────┘   └──────┬───────┘
                                              │
                                              │ HTTP (OpenAI-compatible API)
                                              ▼
                              ┌─────────────────────────────────────┐
                              │  External LLM Providers              │
                              │  (OpenAI, Apple Endor)               │
                              └─────────────────────────────────────┘
```

## Service Responsibilities

### 1. Frontend (Next.js)
**Port:** 3000  
**Technology:** Next.js 16, React 19, TypeScript, Tailwind CSS

#### Primary Responsibilities
- **User Interface**: Chat interface, Tableau view embedding, model selection
- **Client-Side State Management**: Conversation state, message history, UI state
- **API Communication**: REST API calls to backend, SSE connections for streaming
- **MCP Integration**: SSE connection to MCP server for web-based tool access

#### Communication
- **To Backend**: HTTPS REST API (`NEXT_PUBLIC_API_URL`)
  - Chat endpoints: `/api/v1/chat/*`
  - Tableau endpoints: `/api/v1/tableau/*`
  - Gateway proxy: `/api/v1/gateway/*`
- **To MCP Server**: SSE connection to `/mcp/sse` (via backend)

#### Key Files
- `frontend/lib/api.ts` - API client with axios
- `frontend/components/chat/*` - Chat UI components
- `frontend/components/tableau/*` - Tableau integration components

---

### 2. Backend (FastAPI)
**Port:** 8000  
**Technology:** FastAPI, Python 3.11, SQLAlchemy, Alembic

#### Primary Responsibilities
- **REST API Server**: Main API endpoints for frontend
- **Chat Management**: Conversation CRUD, message persistence
- **Tableau Integration**: Wrapper around Tableau REST API
- **MCP Server Integration**: Exposes MCP SSE endpoints for web access
- **Database Operations**: PostgreSQL via SQLAlchemy ORM
- **Gateway Client**: Routes LLM requests to Gateway service

#### Communication
- **From Frontend**: Receives HTTPS requests, returns JSON/SSE responses
- **Gateway Integration**: Gateway endpoints exposed at `/api/v1/gateway/*` (integrated, not separate service)
- **To PostgreSQL**: SQLAlchemy ORM for database operations
- **To Redis**: Token caching (via gateway integration)
- **To MCP Server**: Imports MCP tools/resources (same process)

#### Key Components
- `app/api/chat.py` - Chat endpoints (`/api/v1/chat/*`)
- `app/api/tableau.py` - Tableau endpoints (`/api/v1/tableau/*`)
- `app/services/ai/client.py` - UnifiedAIClient (gateway client)
- `app/main.py` - FastAPI app + MCP SSE endpoints
- `app/core/database.py` - Database connection and session management

#### Example Flow
```python
# Frontend → Backend → Gateway → LLM Provider
Frontend.post("/api/v1/chat/message")
  → Backend receives request
  → Backend calls UnifiedAIClient.chat()
  → UnifiedAIClient sends HTTP POST to Gateway
  → Gateway routes to appropriate LLM provider
  → Response flows back through chain
```

---

### 3. Gateway (Unified LLM Gateway)
**Port:** Integrated into Backend (8000)  
**Endpoints:** `/api/v1/gateway/*`  
**Technology:** FastAPI, Python 3.11, httpx

#### Primary Responsibilities
- **Provider Abstraction**: Single OpenAI-compatible interface for all LLM providers
- **Model Routing**: Resolves model names to providers (e.g., "gpt-4" → OpenAI)
- **Authentication Handling**: Manages different auth strategies:
  - Direct (API keys for OpenAI)
  - Private Key (Apple Endor)
- **Request Translation**: Converts OpenAI format to provider-specific formats
- **Response Normalization**: Converts all responses to OpenAI format
- **Token Caching**: Caches OAuth tokens in Redis (5min TTL buffer)

#### Communication
- **From Backend**: Receives HTTP requests at `/api/v1/gateway/v1/chat/completions`
- **To Redis**: Token caching for OAuth flows
- **To External LLM APIs**: HTTP requests to provider APIs

#### Key Components
- `app/services/gateway/router.py` - Context resolution (model → provider)
- `app/services/gateway/auth/*` - Authentication adapters
- `app/services/gateway/translators/*` - Request/response translators
- `app/services/gateway/cache.py` - Token caching logic
- `app/services/gateway/api.py` - Gateway API endpoints

#### Example Flow
```python
# Backend → Gateway → Provider
Backend sends: POST /v1/chat/completions
  {
    "model": "gpt-4",
    "messages": [...]
  }
  → Gateway resolves: "gpt-4" → OpenAI provider
  → Gateway gets API key from Authorization header
  → Gateway translates request (passthrough for OpenAI)
  → Gateway calls OpenAI API
  → Gateway normalizes response to OpenAI format
  → Gateway returns to Backend
```

#### Supported Providers
- **OpenAI**: GPT-4, GPT-3.5-turbo (direct API key)
- **Anthropic**: Claude models (direct API key)
- **Salesforce**: Einstein GPT, XGen (JWT OAuth + Trust Layer)
- **Vertex AI**: Gemini models (service account JSON)
- **Apple Endor**: Private endpoint (API key)

---

### 4. MCP Server
**Transport:** stdio (IDE) or SSE (web)  
**Technology:** FastMCP, Python 3.11

#### Primary Responsibilities
- **Tool Exposure**: Exposes Tableau operations as MCP tools
- **Conversation Management**: MCP tools for chat operations
- **Authentication**: MCP tools for Tableau authentication
- **Resource Access**: Provides MCP resources (conversations, datasources, views)
- **Protocol Abstraction**: Supports both stdio (IDE) and SSE (web) transports

#### Communication
- **IDE (stdio mode)**: Spawned as subprocess, communicates via stdin/stdout
- **Web (SSE mode)**: Exposed via backend at `/mcp/sse`
- **Backend**: Same process (imports MCP tools)
- **Database**: Direct access via SQLAlchemy
- **Gateway**: Uses backend's gateway client

#### Key Components
- `mcp_server/server.py` - MCP server initialization
- `mcp_server/tools/tableau_tools.py` - Tableau MCP tools
- `mcp_server/tools/chat_tools.py` - Conversation MCP tools
- `mcp_server/tools/auth_tools.py` - Authentication MCP tools
- `mcp_server/resources/conversation_resources.py` - MCP resources

#### Transport Modes

**1. stdio Mode (IDE Integration)**
```
IDE → spawns python -m mcp_server.server
→ MCP protocol over stdin/stdout
→ Tools execute directly
```

**2. SSE Mode (Web Integration)**
```
Frontend → connects to Backend:/mcp/sse
→ Backend imports mcp_server.server
→ SSE events stream MCP protocol
→ Tools execute via backend
```

#### Available Tools
- `tableau_list_datasources` - List Tableau datasources
- `tableau_list_views` - List Tableau views
- `tableau_query_datasource` - Query a datasource
- `tableau_get_view_embed_url` - Get view embedding URL
- `chat_create_conversation` - Create new conversation
- `chat_get_conversation` - Get conversation by ID
- `chat_list_conversations` - List all conversations
- `chat_add_message` - Add message to conversation
- `chat_get_messages` - Get conversation messages
- `auth_tableau_signin` - Authenticate with Tableau
- `auth_get_token` - Get current auth token
- `auth_refresh_token` - Refresh auth token

#### Available Resources
- `conversation://{id}` - Conversation history
- `datasources://list` - Cached datasource list
- `views://list` - Cached view list

---

## Data Flow Examples

### Example 1: User Sends Chat Message

```
1. Frontend → Backend
   POST /api/v1/chat/message
   {
     "conversation_id": 123,
     "content": "List datasources",
     "model": "gpt-4"
   }

2. Backend saves user message to PostgreSQL

3. Backend → Gateway (internal call)
   POST http://localhost:8000/api/v1/gateway/v1/chat/completions
   {
     "model": "gpt-4",
     "messages": [...history...]
   }
   Headers: Authorization: Bearer <OPENAI_API_KEY>

4. Gateway → OpenAI API
   POST https://api.openai.com/v1/chat/completions
   (with OpenAI-specific format)

5. OpenAI → Gateway
   Response in OpenAI format

6. Gateway normalizes response
   (already in OpenAI format, passthrough)

7. Gateway → Backend
   Normalized response

8. Backend saves assistant message to PostgreSQL

9. Backend → Frontend
   Streaming response (SSE) or JSON
```

### Example 2: Frontend Uses MCP Tool via SSE

```
1. Frontend connects to Backend
   EventSource("http://localhost:8000/mcp/sse")

2. Frontend sends MCP tool call
   (via SSE protocol)

3. Backend receives via /mcp/sse endpoint
   (which imports mcp_server.server)

4. MCP Server executes tool
   e.g., tableau_list_datasources()

5. Tool queries Tableau API
   (via TableauClient)

6. Tool returns result

7. Backend streams result via SSE

8. Frontend receives result
```

### Example 3: IDE Uses MCP Tool via stdio

```
1. IDE spawns MCP server
   python -m mcp_server.server

2. IDE sends MCP protocol message
   (via stdin)

3. MCP Server receives message
   (FastMCP handles protocol)

4. MCP Server executes tool
   e.g., chat_create_conversation()

5. Tool creates conversation in PostgreSQL

6. Tool returns result

7. MCP Server sends result
   (via stdout, MCP protocol)

8. IDE receives result
```

### Example 4: Gateway Routes to Salesforce Model

```
1. Backend → Gateway
   POST /v1/chat/completions
   {
     "model": "sfdc-xgen",
     "messages": [...]
   }

2. Gateway resolves context
   "sfdc-xgen" → Salesforce provider, JWT OAuth auth

3. Gateway checks Redis for cached token
   (if expired or missing, generates new JWT)

4. Gateway exchanges JWT for OAuth token
   (caches in Redis with 5min TTL buffer)

5. Gateway translates request
   OpenAI format → Salesforce nested params format
   Adds x-sfdc-app-context header

6. Gateway → Salesforce Models API
   POST with Salesforce-specific format

7. Salesforce → Gateway
   Response in Salesforce format

8. Gateway normalizes response
   Salesforce format → OpenAI format

9. Gateway → Backend
   Normalized OpenAI-format response
```

---

## Infrastructure Services

### PostgreSQL
**Port:** 5432  
**Purpose:** Primary database

**Tables:**
- `conversations` - Chat conversations
- `messages` - Chat messages
- `sessions` - User sessions
- `datasources` - Tableau datasource cache (optional)
- `views` - Tableau view cache (optional)

**Access:**
- Backend: Via SQLAlchemy ORM
- MCP Server: Via SQLAlchemy ORM (same connection pool)

### Redis
**Port:** 6379  
**Purpose:** Token caching

**Usage:**
- Gateway caches OAuth tokens (Salesforce, Vertex AI)
- TTL: 1 hour with 5-minute buffer before expiration
- Reduces authentication overhead by ~95%

**Access:**
- Gateway: Direct access for token caching
- Backend: Indirect (via gateway)

---

## Key Design Patterns

### 1. Gateway Pattern
The Gateway service abstracts all LLM providers behind a single OpenAI-compatible interface. This allows:
- Backend code to be provider-agnostic
- Easy addition of new providers
- Consistent error handling
- Unified token management

### 2. Protocol Abstraction
MCP Server supports multiple transports:
- **stdio**: For IDE integration (Cursor, VS Code)
- **SSE**: For web integration (browser)

Same tools work in both modes, providing "write-once, deploy-anywhere" capability.

### 3. Service Separation
Each service has focused responsibilities:
- Frontend: UI/UX only
- Backend: Business logic and API
- Gateway: LLM provider abstraction
- MCP Server: Protocol and tool exposure

### 4. Internal Communication
Services communicate via HTTP on internal Docker network:
- `http://backend:8000` - Backend service (includes integrated Gateway)
- `postgresql://postgres:5432` - Database
- `redis://redis:6379` - Cache

### 5. Shared Database
Backend and MCP Server share PostgreSQL:
- Same connection pool
- Same models
- Consistent data access

### 6. Token Caching
Gateway caches OAuth tokens in Redis:
- Reduces authentication overhead
- Automatic refresh before expiration
- Shared across gateway instances

---

## Port Summary

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Frontend | 3000 | HTTP | Next.js web application |
| Backend | 8000 | HTTP/SSE | FastAPI main API server (includes Gateway and MCP SSE) |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Token cache |

**Note:** 
- Gateway is integrated into the Backend service and accessed via `/api/v1/gateway/*` on port 8000
- MCP Server SSE endpoints are integrated into the Backend service and accessed via `/mcp/sse` on port 8000

---

## Network Architecture

### External Access
- Frontend: `http://localhost:3000` (public)
- Backend API: `http://localhost:8000` (public, includes Gateway endpoints at `/api/v1/gateway/*`)

### Internal Docker Network
All services communicate on internal Docker network:
- Service discovery via service names (`backend`, `postgres`, `redis`)
- Gateway is integrated into backend, no separate service
- No external network required for inter-service communication
- Ports exposed only for external access

### Security Considerations
- Gateway not directly exposed (accessed via backend proxy)
- Database and Redis not exposed externally
- CORS configured on backend for frontend access
- Credentials stored securely (encrypted, mounted as volumes)

---

## Scalability

### Horizontal Scaling
- **Frontend**: Stateless, can scale horizontally behind load balancer
- **Backend**: Stateless API, can scale horizontally
- **Gateway**: Stateless, can scale horizontally (shared Redis for token cache)
- **MCP Server**: stdio mode scales automatically (one per IDE connection)

### Vertical Scaling
- **PostgreSQL**: Can be scaled with read replicas
- **Redis**: Can be scaled with Redis Cluster

### Load Balancing
- Frontend: Multiple instances behind nginx/Traefik
- Backend: Multiple instances behind load balancer
- Gateway: Multiple instances share Redis token cache

---

## Error Handling

### Error Propagation
Errors flow back through the chain:
```
LLM Provider Error
  → Gateway (normalizes error)
  → Backend (adds context)
  → Frontend (displays user-friendly message)
```

### Retry Logic
- Backend → Gateway: Exponential backoff (3 retries)
- Gateway → Provider: Provider-specific retry logic
- Frontend → Backend: Automatic retry on 5xx errors

### Circuit Breakers
- Gateway implements circuit breakers for provider failures
- Prevents cascading failures
- Automatic recovery after cooldown period

---

## Monitoring and Observability

### Logging
- Centralized logging to `/app/logs/app.log`
- Log rotation (10MB, 5 backups)
- Structured logging with context

### Health Checks
- All services expose `/health` endpoints
- Docker health checks configured
- Kubernetes liveness/readiness probes supported

### Metrics
- Request/response times logged
- Token cache hit/miss rates
- Provider API call counts
- Error rates by service

---

## Future Enhancements

### Planned Improvements
1. **Service Mesh**: Istio/Linkerd for advanced traffic management
2. **Distributed Tracing**: OpenTelemetry for request tracing
3. **Metrics Collection**: Prometheus + Grafana dashboards
4. **API Gateway**: Kong/Traefik for advanced routing
5. **Message Queue**: RabbitMQ/Kafka for async processing

### Architecture Evolution
- Current: Monolithic backend with separate gateway
- Future: Microservices with event-driven architecture
- MCP Server: Foundation for multi-agent system

---

## References

- [Deployment Guide](../deployment/DEPLOYMENT.md) - How to deploy the application
- [MCP Server Deployment](../deployment/MCP_SERVER_DEPLOYMENT.md) - MCP-specific deployment
- [Main README](../../README.md) - Project overview and getting started
