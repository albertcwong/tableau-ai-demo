# Tableau AI Demo

## 📚 Documentation

All documentation has been organized in the [`docs/`](./docs/) directory:

- **[Documentation Index](./docs/README.md)** - Complete documentation guide
- **[PRD](./docs/prd/)** - Product Requirements Document
- **[Architecture](./docs/architecture/)** - System architecture and design docs
- **[Deployment](./docs/deployment/)** - Deployment guides
- **[Sprint Summaries](./docs/sprints/)** - Development sprint documentation

## Quick Start

See [Deployment Guide](./DEPLOYMENT.md) for detailed instructions.

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health
curl http://localhost:3000
```

---

# Tableau AI Demo - Agentic Tableau Interface

AI-powered interface for interacting with Tableau via conversational agents. This demo tool serves as the foundation for a broader Unified Tableau AI Agent Suite.

## Features

- **Chat Interface**: Natural language conversations with Tableau
- **Model Selection**: Support for OpenAI, Gemini, Salesforce LLM Gateway, and Apple Endor
- **Tableau Integration**: List datasources, views, query data, and embed visualizations
- **MCP Server**: Expose tools, conversation endpoints, and authentication via Model Context Protocol
- **Unified LLM Gateway**: Single OpenAI-compatible interface for all LLM providers

## Tech Stack

### Frontend
- Next.js 16.1.6 (App Router)
- React 19
- TypeScript 5.7
- Tailwind CSS 4.1
- shadcn/ui

### Backend
- FastAPI 0.128.0
- Python 3.12+
- PostgreSQL 15
- Redis 7
- SQLAlchemy 2.0
- Alembic 1.18

## Prerequisites

- **Node.js**: ≥20.9.0
- **Python**: ≥3.12
- **Docker**: For PostgreSQL and Redis services
- **PostgreSQL**: 15+ (via Docker)
- **Redis**: 7+ (via Docker)

## Quick Start

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
# - TABLEAU_SERVER_URL and credentials
# - AI provider API keys
```

### 3. Start Infrastructure Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d

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
│   │   └── main.py          # FastAPI app entry
│   ├── mcp_server/          # MCP Server implementation
│   ├── alembic/             # Database migrations
│   └── tests/               # Test suite
│
├── credentials/             # Service account credentials (gitignored)
├── docker-compose.yml       # Infrastructure services
└── .env.example            # Environment variable template
```

## Development

### Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate
pytest

# Frontend tests
cd frontend
npm test
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

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `TABLEAU_SERVER_URL`: Tableau server URL
- `TABLEAU_CLIENT_ID` / `TABLEAU_CLIENT_SECRET`: Tableau Connected App credentials
- `OPENAI_API_KEY`: OpenAI API key
- `GATEWAY_BASE_URL`: Unified LLM Gateway URL

## Architecture

The application uses a microservices architecture:

1. **Frontend**: Next.js web application
2. **Backend**: FastAPI REST API
3. **MCP Server**: Model Context Protocol server for IDE/web integration
4. **Unified LLM Gateway**: Single interface for all LLM providers
5. **PostgreSQL**: Database for conversations and metadata
6. **Redis**: Token caching for OAuth flows

## Next Steps

- Phase 2: Database Schema (conversations, messages, sessions)
- Phase 3: Tableau Integration (REST API client, endpoints)
- Phase 4: Unified LLM Gateway (authentication, translators)
- Phase 5: Chat Interface (frontend components, backend API)
- Phase 6: MCP Server (tools, resources, authentication)

## License

[Your License Here]

## Contributing

[Contributing Guidelines]
