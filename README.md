# Tableau AI Demo

AI-powered interface for interacting with Tableau via conversational agents. This demo tool demonstrates agentic capabilities like reasoning, planning, and decision-making through natural language interactions with Tableau datasources and views.

## Current State

### Implemented Features

- **Chat Interface**: Natural language conversations with Tableau
  - Conversation history persistence
  - Streaming responses
  - Context management (add/remove datasources and views)
  
- **Model Selection**: Currently supported LLM providers
  - OpenAI (GPT-4, GPT-3.5-turbo)
  - Apple Endor (private endpoint)

- **Tableau Integration**:
  - List datasources
  - List views
  - Query datasources via VizQL Data Service
  - Embed Tableau views
  - Get datasource schemas
  - Schema enrichment with VizQL metadata

- **Multi-Agent System**:
  - **VizQL Agent**: Constructs and executes VizQL queries from natural language
    - LangGraph-based ReAct pattern
    - Query planning, validation, refinement loops
    - Semantic rules engine for field suggestions
    - Constraint validation (MEASURE/DIMENSION)
  - **Summary Agent**: Exports and summarizes data from multiple views
    - Multi-view data export
    - LLM-powered summarization
    - Report generation
  - **General Agent**: General-purpose Tableau interaction
  - **Meta Agent Router**: Intent classification and agent selection

- **MCP Server**: Model Context Protocol implementation
  - Exposes Tableau operations as MCP tools
  - Conversation management via MCP
  - Authentication via MCP
  - Supports stdio (IDE) and SSE (web) transports
  - Available in Cursor, VS Code, and web interfaces

- **Admin Interface**:
  - User management
  - Tableau server configuration
  - Auth configuration management
  - Settings management

- **Authentication**:
  - OAuth 2.0 Connected Apps (JWT)
  - Auth0 integration for username mapping
  - Token caching in Redis
  - Session management

- **Unified LLM Gateway**:
  - Single OpenAI-compatible interface for LLM providers
  - Currently supports OpenAI and Apple Endor
  - Request/response translation
  - Token caching
  - Provider abstraction (architecture supports additional providers)

### Architecture

**Frontend:**
- Next.js 16.1.6 (App Router)
- React 19
- TypeScript 5.7
- Tailwind CSS 4.1
- shadcn/ui components

**Backend:**
- FastAPI 0.128.0
- Python 3.12+
- PostgreSQL 15 (via Docker)
- Redis 7 (via Docker)
- SQLAlchemy 2.0
- Alembic 1.18

**Agents:**
- LangGraph for state management
- ReAct pattern (Reason-Act-Observe)
- Tool orchestration
- Error recovery and retry logic

**MCP:**
- FastMCP server
- stdio transport for IDE integration
- SSE transport for web integration

### Testing Status

- **Unit Tests**: Model tests, agent node tests, gateway tests
- **Integration Tests**: MCP flow tests, chat API tests, multi-agent tests
- **Test Coverage**: Tests exist for core functionality; coverage metrics available via pytest-cov

## Quick Start

### Prerequisites

- **Node.js**: ≥20.9.0
- **Python**: ≥3.12
- **Docker**: For PostgreSQL and Redis services
- **PostgreSQL**: 15+ (via Docker)
- **Redis**: 7+ (via Docker)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd tableau-ai-demo
```

### 2. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# At minimum, set:
# - DATABASE_URL
# - REDIS_URL
# - SECRET_KEY
# - AUTH0_SECRET
```

### 3. Start Infrastructure Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Verify services are running
docker-compose ps
```

### 4. Backend Setup

```bash
cd backend

# Create virtual environment (Python 3.12+)
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload --port 8000
```

Backend will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

**Note**: For Tableau authentication, HTTPS is required. See [HTTPS Setup](./docs/deployment/HTTPS_SETUP.md) for development certificate setup.

## Project Structure

```
├── frontend/                 # Next.js application
│   ├── app/                  # App Router pages
│   ├── components/          # React components
│   ├── lib/                  # Utilities and API client
│   └── types/               # TypeScript types
│
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/             # API routes
│   │   ├── core/            # Configuration, database, cache
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   │   ├── agents/      # Agent implementations
│   │   │   ├── gateway/     # Unified LLM Gateway
│   │   │   └── tableau/     # Tableau client
│   │   └── main.py          # FastAPI app entry
│   ├── mcp_server/          # MCP Server implementation
│   ├── alembic/             # Database migrations
│   └── tests/               # Test suite
│
├── credentials/             # Service account credentials (gitignored)
│   └── .gitkeep            # Placeholder for service account files
├── backend/mcp_server/credentials/  # MCP server credential storage (gitignored)
│   ├── .mcp_key.key        # Encryption key for MCP credentials
│   └── .mcp_auth.json      # Encrypted MCP credentials
├── docker-compose.yml       # Infrastructure services
└── .env.example            # Environment variable template
```

## Features

### Chat Interface

- Natural language conversations with Tableau
- Conversation history with persistence
- Streaming responses
- Context management (datasources and views)
- Agent selection (VizQL, Summary, General)

### Tableau Operations

- **Datasources**: List, query, get schema, enrich metadata
- **Views**: List, embed, export data, export crosstab
- **VizQL Queries**: Natural language to VizQL conversion
- **Authentication**: OAuth 2.0 Connected Apps

### Multi-Agent System

- **VizQL Agent**: Specialized for query construction and execution
- **Summary Agent**: Specialized for multi-view analysis and summarization
- **General Agent**: General-purpose Tableau interaction
- **Meta Router**: Intelligent agent selection based on user intent

### MCP Integration

- Tools exposed via Model Context Protocol
- IDE integration (Cursor, VS Code) via stdio
- Web integration via SSE
- Conversation management via MCP
- Authentication via MCP

## Development

### Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate
pytest

# Run specific test suite
pytest tests/unit/agents/vizql/ -v
pytest tests/integration/ -v

# With coverage
pytest --cov=app --cov-report=html
```

### Database Migrations

```bash
cd backend
source venv/bin/activate

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Code Quality

```bash
# Backend linting
cd backend
source venv/bin/activate
ruff check .
black .

# Frontend linting
cd frontend
npm run lint
```

## Environment Variables

See `.env.example` for all available configuration options. Key variables:

**Required:**
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Secret key for session encryption
- `AUTH0_SECRET`: Auth0 cookie secret (32+ chars)

**Optional (configured via Admin UI):**
- `TABLEAU_SERVER_URL`: Tableau server URL
- `TABLEAU_CLIENT_ID` / `TABLEAU_CLIENT_SECRET`: Tableau Connected App credentials
- `OPENAI_API_KEY`: OpenAI API key (for OpenAI models)
- `APPLE_ENDOR_API_KEY`: Apple Endor API key (for Endor models)
- `GATEWAY_BASE_URL`: Unified LLM Gateway URL

**Note**: Most configuration is managed via the Admin interface. Only bootstrap variables (database, cache, secrets) are required in `.env`.

## Deployment

See [Deployment Guide](./docs/deployment/DEPLOYMENT.md) for detailed deployment instructions.

### Docker Compose

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health
curl http://localhost:3000
```

### Production Considerations

- Use secrets management for credentials
- Enable HTTPS with proper SSL certificates
- Configure CORS properly
- Set up monitoring and logging
- Use production-grade PostgreSQL and Redis

## Architecture

The application uses a microservices architecture:

1. **Frontend**: Next.js web application
2. **Backend**: FastAPI REST API
3. **MCP Server**: Model Context Protocol server for IDE/web integration
4. **Unified LLM Gateway**: Single interface for LLM providers (currently OpenAI and Apple Endor)
5. **PostgreSQL**: Database for conversations and metadata
6. **Redis**: Token caching for OAuth flows

See [Architecture Documentation](./docs/architecture/ARCHITECTURE.md) for detailed architecture information.

## TODOs

Based on PRD requirements (`prd.txt`):

### Completed ✅

- ✅ Chat interface
- ✅ Chat history
- ✅ Model selection
- ✅ List datasources
- ✅ List views
- ✅ Query datasources
- ✅ Embed views

### In Progress / Needs Verification ⏳

- ⏳ **Unit Tests**: PRD requires unit tests. Current status:
  - Unit tests exist for models, agents, gateway
  - Integration tests exist for MCP, chat API
  - Need to verify coverage meets PRD requirements
  - Need to ensure all critical paths are tested

### Future Enhancements (from detailed PRD)

The detailed PRD (`docs/prd/PRD_ AI Agent Suite for Tableau.md`) outlines a broader vision:

- **Administrator Agent**: Zombie content cleanup, security auditing
- **Creator Agent**: XML manipulation, LOD generation, style enforcement
- **Steward Agent**: Impact analysis, automated warnings
- **Analyst Agent Refactor**: Headless BI, Chat-to-Viz with Embedding API v3

These are future phases beyond the current demo scope.

## Documentation

### Essential Documentation

- [Architecture](./docs/architecture/ARCHITECTURE.md) - System architecture
- [Multi-Agent Architecture](./docs/architecture/MULTI_AGENT_ARCHITECTURE.md) - Agent system design
- [Deployment Guide](./docs/deployment/DEPLOYMENT.md) - Deployment instructions
- [MCP Server Deployment](./docs/deployment/MCP_SERVER_DEPLOYMENT.md) - MCP-specific deployment
- [HTTPS Setup](./docs/deployment/HTTPS_SETUP.md) - Frontend HTTPS configuration
- [Auth0 Setup](./docs/AUTH0_TABLEAU_METADATA_SETUP.md) - Auth0 metadata configuration
- [OAuth Setup](./docs/OAUTH_2_0_TRUST_SETUP.md) - OAuth 2.0 Connected App setup

### Component-Specific Documentation

- [Backend README](./backend/README.md) - Backend-specific documentation
- [Frontend README](./frontend/README.md) - Frontend-specific documentation
- [MCP Server README](./backend/mcp_server/README.md) - MCP server documentation
- [MCP Troubleshooting](./backend/mcp_server/TROUBLESHOOTING.md) - MCP troubleshooting guide
- [Integration Tests](./backend/tests/integration/README.md) - Integration test guide

## License

[Your License Here]

## Contributing

[Contributing Guidelines]
