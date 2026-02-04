# Agentic Tableau Demo Tool - Implementation Plan

## Overview
Build an AI-powered interface for interacting with Tableau via conversational agents. The system will demonstrate agentic capabilities like reasoning, planning, and decision-making through natural language interactions with Tableau datasources and views.

**Strategic Context:** This demo tool serves as the foundation for a broader **Unified Tableau AI Agent Suite** that will include Administrator, Creator, Steward, and Analyst agents. To support this future expansion, the architecture will expose core capabilities via **Model Context Protocol (MCP)**, enabling "write-once, deploy-anywhere" integration with IDEs (VS Code, Cursor) and web interfaces.

## Core Features

### User-Facing Features
- Chat interface with conversation history
- Model selection (OpenAI, Gemini, Salesforce LLM Gateway, Apple Endor)
- List Tableau datasources
- List Tableau views
- Query Tableau datasources
- Embed Tableau views

### Browser UI for Tableau Object Explorer
**Purpose:** Provide a visual interface to explore and interact with Tableau objects in a file-explorer-like experience.

#### Object Explorer
- **Connection Interface**: Allow users to connect to a Tableau site
- **Hierarchical Navigation**: Browse Tableau objects with a file explorer experience:
  - **Projects**: Act as directories containing other objects
  - **Published Datasources**: Act as files within projects
  - **Workbooks**: Act as files within projects
  - **Views**: Act as files within workbooks
- **Breadcrumb Navigation**: Display current location in the object hierarchy
- **Object Interaction**: Click on objects to view details:
  - **Published Datasources**: Display schema and sample data
  - **Projects**: Display contents and update breadcrumbs
  - **Views**: Embed and render the view in a component

#### Agent Assistant Panel
- **Side Panel Toggle**: Message interface that can be shown/hidden
- **Context Integration**: Bring Tableau objects into chat context:
  - **Published Datasources**: For VizQL agent queries
  - **Views**: For summary agent analysis
- **Agent Selection**: Dropdown to choose between available agents
- **Model Configuration**: Settings interface for providers and models (infrequently adjusted)
- **Chat Management**:
  - Start new chat threads
  - Select historical chat threads
  - Preserve conversation context across sessions

### MCP Integration (Foundation for Agent Suite) ⭐
**Critical Requirement:** All core capabilities must be exposed via Model Context Protocol (MCP) to enable:
- **IDE Integration**: Direct access from Cursor, VS Code via stdio transport
- **Web Integration**: HTTP access via Server-Sent Events (SSE) transport
- **Agent Suite Reusability**: Foundation for future Administrator, Creator, and Steward agents

**Exposed via MCP:**
- **Tools**: Tableau operations (list/query datasources, embed views)
- **Conversation Management**: Create/read/update conversation history
- **Authentication**: Tableau Connected App authentication with secure credential storage

## Tech Stack

### Frontend
- **Framework**: Next.js (App Router)
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui
- **Linting**: ESLint 9
- **Language**: TypeScript
- **Node.js**: ≥20.9.0 (required for Next.js 16)

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Cache**: Redis (for token caching)
- **Language**: Python ≥3.10 (required for uvicorn 0.40+, redis 7.1+, fastmcp 2.14+)

### AI Integration (via Unified LLM Gateway)
- **Gateway Architecture**: Single OpenAI-compatible interface for all models
- **Direct Passthrough**: OpenAI, Anthropic (API keys)
- **Salesforce Models API**: Einstein Platform (JWT OAuth, Trust Layer)
- **Vertex AI**: Google Gemini (Service Account JSON)
- **Apple Endor**: Private endpoint routing
- **Token Management**: Cached OAuth tokens (Redis) with automatic refresh

### MCP Server ⭐
- **Framework**: FastMCP (Python)
- **Protocol**: Model Context Protocol (MCP)
- **Transports**: stdio (IDE), SSE (Web)
- **Purpose**: Expose Tableau tools, conversation management, and authentication as reusable MCP resources

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT INTERFACES                             │
├──────────────────────────────┬──────────────────────────────────────┤
│   IDEs (Cursor, VS Code)     │    Web Frontend (Next.js)           │
│   [Developer/Admin Users]    │    [Analyst/Business Users]         │
└──────────────┬───────────────┴───────────────┬──────────────────────┘
               │                               │
               │ stdio                         │ HTTPS/SSE
               │                               │
┌──────────────▼───────────────────────────────▼──────────────────────┐
│                         MCP SERVER                                   │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Tools Layer                                                │    │
│  │  • tableau_list_datasources    • chat_create_conversation  │    │
│  │  • tableau_list_views          • chat_add_message          │    │
│  │  • tableau_query_datasource    • auth_tableau_signin       │    │
│  │  • tableau_get_view_embed_url  • auth_refresh_token        │    │
│  └────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Resources Layer                                            │    │
│  │  • conversation://{id}     • datasources://list            │    │
│  │  • views://list                                             │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────┬────────────────────────────────┬──────────────────────┘
               │                                │
               │ Internal API                   │ Database Queries
               │                                │
┌──────────────▼────────────────┐  ┌───────────▼──────────────────────┐
│     FastAPI Backend           │  │      PostgreSQL Database         │
│  • Chat API                   │  │  • Conversations                 │
│  • Tableau Client Wrapper     │  │  • Messages                      │
│  • AI Service (Gateway Client)│  │  • Sessions                      │
└──────────────┬────────────────┘  └──────────────────────────────────┘
               │
               │ OpenAI-compatible API
               │
┌──────────────▼───────────────────────────────────────────────────────┐
│               UNIFIED LLM GATEWAY (Internal Service)                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Context Resolution: model name → provider + auth strategy  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐    │
│  │ Direct Auth  │ JWT OAuth    │ Service Acct │ Private Key  │    │
│  │ (API Keys)   │ (Salesforce) │ (Vertex AI)  │ (Apple)      │    │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘    │
│         │              │              │              │             │
│  ┌──────▼──────────────▼──────────────▼──────────────▼───────┐    │
│  │           Token Cache (Redis) - 5min TTL buffer           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐    │
│  │   OpenAI     │  Salesforce  │  Vertex AI   │   Anthropic  │    │
│  │  Translator  │  Translator  │  Translator  │  Translator  │    │
│  │ (passthrough)│  (nested     │ (contents/   │ (passthrough)│    │
│  │              │  params)     │  parts)      │              │    │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘    │
└─────────┼──────────────┼──────────────┼──────────────┼──────────────┘
          │              │              │              │
┌─────────▼────┐  ┌──────▼────────┐  ┌─▼────────────┐  ┌─▼──────────┐
│ OpenAI API   │  │ Salesforce    │  │ Vertex AI    │  │ Anthropic  │
│ (GPT-4, etc) │  │ Models API    │  │ (Gemini)     │  │ (Claude)   │
│              │  │ +Trust Layer  │  │              │  │            │
└──────────────┘  └───────────────┘  └──────────────┘  └────────────┘
          │                                │
          │ REST API / GraphQL             │
          │                                │
┌─────────▼────────────────────────────────▼──────────────────────────┐
│   Tableau Server                                                     │
│  • REST API                                                          │
│  • Metadata API (GraphQL)                                            │
│  • Connected Apps (JWT)                                              │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**
1. **Protocol-First**: MCP server is the primary interface for all agents
2. **Transport Agnostic**: Same tools work via stdio (IDE) and SSE (web)
3. **Stateless Tools**: Tools are idempotent and stateless where possible
4. **Secure by Default**: Authentication tokens encrypted, HITL for destructive actions
5. **Future-Ready**: Architecture supports Admin, Creator, Steward agents without changes
6. **Unified AI Gateway**: Single OpenAI-compatible interface abstracts all LLM providers
7. **Token Management**: Cached OAuth tokens (Redis) with automatic refresh and 5-min TTL buffer
8. **Request Normalization**: All responses normalized to OpenAI format for agent consistency

## Project Structure

```
├── frontend/                 # Next.js application
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx         # Main chat interface
│   │   ├── agents/          # NEW: Multi-agent dashboard
│   │   │   ├── page.tsx     # Agent selector dashboard
│   │   │   ├── layout.tsx   # Shared agent layout
│   │   │   └── [agentId]/   # Individual agent views
│   │   │       └── page.tsx
│   │   └── api/             # Next.js API routes (if needed)
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── chat/
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── ModelSelector.tsx
│   │   ├── agents/          # NEW: Agent-specific components
│   │   │   ├── AgentSelector.tsx
│   │   │   ├── VizQLPanel.tsx
│   │   │   ├── SummaryPanel.tsx
│   │   │   ├── SchemaViewer.tsx
│   │   │   ├── QueryBuilder.tsx
│   │   │   ├── ViewSelector.tsx
│   │   │   ├── ExportOptions.tsx
│   │   │   └── ResultViewer.tsx
│   │   └── tableau/
│   │       ├── ViewEmbedder.tsx
│   │       └── DataSourceList.tsx
│   ├── lib/
│   │   ├── api.ts           # API client
│   │   ├── agents.ts        # NEW: Agent API client
│   │   └── tableau.ts       # Tableau utilities
│   ├── types/
│   │   ├── index.ts
│   │   └── agents.ts        # NEW: Agent types
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── next.config.js
│   └── package.json
│
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app entry
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py      # Chat endpoints
│   │   │   ├── tableau.py   # Tableau endpoints
│   │   │   ├── agents.py    # NEW: Agent endpoints
│   │   │   └── models.py    # API models
│   │   ├── core/
│   │   │   ├── config.py    # Configuration
│   │   │   ├── database.py  # PostgreSQL connection
│   │   │   └── cache.py     # Redis connection
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py      # Base AI service interface
│   │   │   │   └── client.py    # Unified client (talks to gateway)
│   │   │   ├── agents/      # NEW: Agent implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py        # Master agent router
│   │   │   │   ├── vds_agent.py     # VizQL agent
│   │   │   │   ├── summary_agent.py # Summary agent
│   │   │   │   └── analyst_agent.py # Existing analyst (refactored)
│   │   │   ├── gateway/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py    # Main gateway router
│   │   │   │   ├── auth/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── direct.py       # API key passthrough
│   │   │   │   │   ├── salesforce.py   # JWT OAuth flow
│   │   │   │   │   └── vertex.py       # Service account flow
│   │   │   │   ├── translators/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── openai.py       # OpenAI format (passthrough)
│   │   │   │   │   ├── salesforce.py   # SFDC adapter
│   │   │   │   │   └── vertex.py       # Vertex AI adapter
│   │   │   │   └── cache.py            # Token caching logic
│   │   │   └── tableau/
│   │   │       ├── __init__.py
│   │   │       ├── client.py    # Tableau REST API client
│   │   │       ├── vizql.py     # NEW: VizQL query execution
│   │   │       ├── export.py    # NEW: Data export
│   │   │       ├── datasource.py
│   │   │       └── view.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── chat.py      # Chat history models
│   │       └── session.py
│   ├── mcp_server/          # MCP Server (separate from FastAPI)
│   │   ├── __init__.py
│   │   ├── server.py        # Main MCP server entry
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── tableau_tools.py   # Tableau MCP tools
│   │   │   ├── vizql_tools.py     # NEW: VizQL MCP tools
│   │   │   ├── export_tools.py    # NEW: Export MCP tools
│   │   │   ├── chat_tools.py      # Conversation MCP tools
│   │   │   └── auth_tools.py      # Authentication MCP tools
│   │   ├── resources/
│   │   │   ├── __init__.py
│   │   │   └── conversation.py    # Conversation history resources
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── analyst.py         # Analyst agent prompts
│   │       ├── vds_agent.py       # NEW: VizQL agent prompts
│   │       └── summary_agent.py   # NEW: Summary agent prompts
│   ├── alembic/             # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── credentials/             # Service account credentials (gitignored)
│   ├── .gitkeep
│   └── vertex-sa.json.example
├── .env.example
├── docker-compose.yml       # PostgreSQL + Redis + app services
├── .gitignore
└── README.md
```

## Implementation Phases

### Phase 1: Project Setup & Infrastructure
1. **Initialize Next.js Frontend**
   - Create Next.js app with TypeScript
   - Configure Tailwind CSS
   - Install and configure shadcn/ui
   - Set up ESLint 9
   - Configure project structure

2. **Initialize FastAPI Backend**
   - Create FastAPI application structure
   - Set up PostgreSQL connection
   - Configure database models (SQLAlchemy)
   - Set up Alembic for migrations
   - Create basic API structure

3. **Environment Configuration**
   - Create `.env.example` with all required variables
   - Set up environment variable management
   - Configure CORS for frontend-backend communication
   - Configure MCP server credentials

### Phase 2: Database Schema
1. **Chat History Models**
   - `conversations` table (id, created_at, updated_at)
   - `messages` table (id, conversation_id, role, content, model_used, created_at)
   - `sessions` table (id, user_id, created_at, last_active)

2. **Tableau Metadata Cache** (optional optimization)
   - `datasources` table (id, tableau_id, name, project, updated_at)
   - `views` table (id, tableau_id, name, workbook, datasource_id, updated_at)

### Phase 3: Tableau Integration
1. **Tableau REST API Client**
   - Authentication (JWT/Connected App)
   - List datasources endpoint
   - List views endpoint
   - Query datasource endpoint (using Tableau Data API or REST API)
   - Get view embedding URL

2. **Backend API Endpoints**
   - `GET /api/tableau/datasources` - List all datasources
   - `GET /api/tableau/views` - List all views (optionally filtered by datasource)
   - `POST /api/tableau/query` - Query a datasource
   - `GET /api/tableau/views/{view_id}/embed-url` - Get embedding URL

3. **Frontend Tableau Components**
   - `ViewEmbedder` - Component to embed Tableau views using Embedding API v3
   - `DataSourceList` - Display list of datasources
   - `ViewList` - Display list of views

### Phase 4: Unified LLM Gateway & AI Integration
1. **Gateway Core Infrastructure**
   - Create gateway routing logic with context resolution
   - Set up Redis for token caching
   - Implement strategy pattern for provider selection
   - Configure OpenAI-compatible interface

2. **Authentication Adapters**
   - **Direct Passthrough**: API key injection for OpenAI/Anthropic
   - **Salesforce JWT OAuth**: Connected App flow with Trust Layer headers
   - **Vertex AI Service Account**: JSON credential loading and JWT signing
   - **Token Caching**: Redis-based cache with 5-minute TTL buffer

3. **Request/Response Translators**
   - **OpenAI Translator**: Passthrough (no transformation)
   - **Salesforce Translator**: Nested parameters format + x-sfdc-app-context header
   - **Vertex AI Translator**: Convert messages to contents/parts format
   - **Response Normalizer**: Unify all responses to OpenAI choices[0].message format

4. **AI Service Client**
   - Create unified AI client that talks to gateway
   - Implement streaming support
   - Handle function calling across providers
   - Token usage tracking and error handling

5. **Model Configuration**
   - Model-to-provider mapping (e.g., "gpt-4" → OpenAI, "gemini-pro" → Vertex)
   - Credential management (API keys, JWT secrets, service account JSON)
   - Fallback model configuration

### Phase 5: Chat Interface
1. **Backend Chat API**
   - `POST /api/chat/message` - Send message, get AI response
   - `GET /api/chat/conversations` - List conversations
   - `GET /api/chat/conversations/{id}/messages` - Get conversation history
   - `POST /api/chat/conversations` - Create new conversation
   - WebSocket support for streaming responses (optional)

2. **Frontend Chat Components**
   - `ChatInterface` - Main chat container
   - `MessageList` - Display messages with history
   - `MessageInput` - Input field with send button
   - `ModelSelector` - Dropdown to select AI model
   - Message rendering (text, Tableau views, datasource results)

3. **Chat State Management**
   - Conversation context management
   - Message history persistence
   - Loading states
   - Error handling

### Phase 5A: Tableau Object Explorer UI
1. **Backend API Extensions**
   - `GET /api/tableau/projects` - List all projects with hierarchy
   - `GET /api/tableau/projects/{id}/contents` - Get contents of a project (datasources, workbooks, nested projects)
   - `GET /api/tableau/workbooks` - List all workbooks
   - `GET /api/tableau/workbooks/{id}/views` - List views within a workbook
   - `GET /api/tableau/datasources/{id}/schema` - Get datasource schema (columns, data types)
   - `GET /api/tableau/datasources/{id}/sample` - Get sample data from datasource

2. **Object Explorer Components**
   - `ObjectExplorer` - Main container with file-explorer layout
   - `ProjectTree` - Hierarchical tree view of projects
   - `ObjectList` - List view showing datasources/workbooks/views in current location
   - `BreadcrumbNav` - Navigation breadcrumbs showing current path
   - `ObjectIcon` - Icon component for different object types (project, datasource, workbook, view)

3. **Object Detail Panels**
   - `DatasourceDetail` - Display schema table and sample data grid
   - `ViewDetail` - Embedded view renderer using Tableau Embedding API v3
   - `ProjectDetail` - Display project metadata and contents
   - `WorkbookDetail` - Display workbook metadata and contained views

4. **Navigation State Management**
   - Current location tracking (project path)
   - Breadcrumb history
   - Selected object state
   - Loading states for async operations

### Phase 5B: Agent Assistant Side Panel
1. **Backend API Extensions**
   - `POST /api/chat/context/add-datasource` - Add datasource to chat context
   - `POST /api/chat/context/add-view` - Add view to chat context
   - `GET /api/chat/context` - Get current chat context objects
   - `DELETE /api/chat/context/{object_id}` - Remove object from context

2. **Side Panel Components**
   - `AgentPanel` - Main container with toggle functionality
   - `AgentSelector` - Dropdown for selecting agent type (VizQL, Summary, General)
   - `ContextManager` - Display and manage objects in chat context
   - `ContextItem` - Individual context item with remove button
   - `ModelSettings` - Collapsible settings panel for provider/model configuration

3. **Chat Thread Management**
   - `ThreadList` - List of historical chat threads
   - `ThreadItem` - Individual thread with preview and timestamp
   - `NewThreadButton` - Create new chat thread
   - `ThreadSwitcher` - Switch between active threads

4. **Integration with Object Explorer**
   - Context menu on objects with "Add to Chat" action
   - Drag-and-drop objects into chat panel
   - Visual indicator when objects are in context
   - Automatic context type routing (datasources → VizQL agent, views → Summary agent)

5. **Panel State Management**
   - Panel open/closed state
   - Selected agent type
   - Active thread ID
   - Context objects list
   - Model/provider settings persistence

### Phase 6: MCP Server Implementation ⭐ **Critical for Agent Suite**
1. **MCP Server Setup**
   - Initialize FastMCP server
   - Configure stdio transport for IDE integration (Cursor, VS Code)
   - Configure SSE transport for web integration
   - Set up connection management

2. **MCP Tools (Tableau Operations)**
   - `tableau_list_datasources` - List all datasources
   - `tableau_list_views` - List all views
   - `tableau_query_datasource` - Query a datasource with filters
   - `tableau_get_view_embed_url` - Get embedding URL for a view
   - Tool schema definitions with JSON Schema

3. **MCP Tools (Conversation Management)**
   - `chat_create_conversation` - Create new conversation
   - `chat_get_conversation` - Get conversation by ID
   - `chat_list_conversations` - List all conversations
   - `chat_add_message` - Add message to conversation
   - `chat_get_messages` - Get conversation history

4. **MCP Resources**
   - `conversation://{id}` - Access conversation history as resource
   - `datasources://list` - Access cached datasource list
   - `views://list` - Access cached view list

5. **MCP Authentication**
   - `auth_tableau_signin` - Authenticate with Tableau Connected Apps
   - `auth_get_token` - Get current auth token
   - `auth_refresh_token` - Refresh expired token
   - Store credentials securely (encrypted, not plaintext)

### Phase 7: Agentic Capabilities
1. **Intent Recognition**
   - Parse user queries to identify actions:
     - List datasources
     - List views
     - Query datasource
     - Embed view
     - General questions

2. **Function Calling / Tool Use**
   - Implement function calling for AI models that support it
   - Tools: `list_datasources`, `list_views`, `query_datasource`, `embed_view`
   - Tool execution and result formatting

3. **Reasoning & Planning**
   - Multi-step query planning
   - Context-aware responses
   - Follow-up question handling

### Phase 8: UI/UX Polish
1. **Styling & Layout**
   - Responsive design
   - Dark mode support (optional)
   - Loading indicators
   - Error states
   - Empty states

2. **User Experience**
   - Keyboard shortcuts
   - Message editing/deletion
   - Conversation management (rename, delete)
   - Export conversation history

### Phase 9: Testing & Deployment
1. **Testing**
   - Unit tests for backend services
   - Integration tests for API endpoints
   - Frontend component tests
   - E2E tests for critical flows

2. **Deployment**
   - Docker containerization
   - Environment-specific configurations
   - CI/CD pipeline setup
   - Documentation

## Technical Considerations

### Authentication & Security
- Tableau authentication via Connected App (JWT)
- **Unified Gateway Security**:
  - API keys never exposed to agents (handled by gateway)
  - Service account JSON files stored in `credentials/` (gitignored)
  - Salesforce Trust Layer integration (PII masking via `x-sfdc-app-context` header)
  - OAuth tokens cached in Redis with 5-minute TTL buffer
  - Token rotation via Secret Manager (AWS/GCP) in production
- Rate limiting on API endpoints
- Credential encryption at rest

### Performance
- Cache Tableau metadata (datasources, views)
- **Redis-based token caching**: OAuth tokens cached to avoid repeated auth flows
- Implement pagination for large lists
- Optimize database queries
- Lazy load embedded views
- Gateway connection pooling for backend providers

### Error Handling
- Graceful degradation when AI providers are unavailable
- Clear error messages for users
- Retry logic for transient failures
- Logging and monitoring

### Scalability
- Database connection pooling
- Async request handling
- Consider Redis for caching (future)
- Horizontal scaling support

## Dependencies

### Frontend
- `next`: ^16.1.6 (Latest stable with Turbopack, Cache Components)
- `react`: ^19.0.0 (React 19 stable)
- `typescript`: ^5.7.0 (Latest TypeScript, included with Next.js)
- `tailwindcss`: ^4.1.0 (Tailwind CSS v4 with new PostCSS structure)
- `@radix-ui/*`: shadcn/ui dependencies (latest versions)
- `axios` or `fetch`: API client (native fetch preferred)

### Backend
- `fastapi`: ^0.128.0 (Latest, requires Python ≥3.9)
- `uvicorn`: ^0.40.0 (Latest ASGI server, requires Python ≥3.10)
- `sqlalchemy`: ^2.0.46 (Latest stable 2.0 series)
- `alembic`: ^1.18.3 (Latest migrations tool)
- `psycopg2-binary`: ^2.9.11 (Latest PostgreSQL driver)
- `redis`: ^7.1.0 (Latest Redis Python client, requires Python ≥3.10)
- `pydantic`: ^2.12.5 (Latest Pydantic v2, requires Python ≥3.9)
- `python-dotenv`: ^1.2.1 (Latest environment variable loader)
- `openai`: ^2.16.0 (Latest OpenAI Python SDK)
- `httpx`: ^0.28.1 (Latest async HTTP client)
- `pyjwt`: ^2.10.1 (Latest JWT library, requires Python ≥3.9)
- `google-auth`: ^2.48.0 (Latest Google authentication, requires Python ≥3.8)
- `cryptography`: ^46.0.4 (Latest cryptographic library, requires Python ≥3.8)
- `tableauserverclient`: ^0.38.0 (Latest Tableau REST API client)
- `fastmcp`: ^2.14.4 (Latest FastMCP framework, requires Python ≥3.10)

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tableau_demo

# Redis (Token Cache)
REDIS_URL=redis://localhost:6379/0
REDIS_TOKEN_TTL=3600  # 1 hour, cached with 5min buffer

# Tableau
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_SITE_ID=your-site-id
TABLEAU_CLIENT_ID=your-connected-app-client-id
TABLEAU_CLIENT_SECRET=your-connected-app-secret

# Unified LLM Gateway Configuration
GATEWAY_ENABLED=true
GATEWAY_BASE_URL=http://gateway:8001  # Internal gateway service
GATEWAY_PORT=8001

# AI Provider Credentials (Direct Passthrough)
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# Salesforce Models API (JWT OAuth)
SALESFORCE_CLIENT_ID=your-connected-app-client-id
SALESFORCE_PRIVATE_KEY_PATH=./credentials/salesforce-private-key.pem
SALESFORCE_USERNAME=your-service-account@company.com
SALESFORCE_MODELS_API_URL=https://api.salesforce.com/einstein/platform/v1

# Vertex AI (Service Account)
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=us-central1
VERTEX_SERVICE_ACCOUNT_PATH=./credentials/vertex-sa.json

# Apple Endor (Private Endpoint)
APPLE_ENDOR_API_KEY=your-apple-key
APPLE_ENDOR_ENDPOINT=https://internal.apple.com/endor/v1

# Application
NEXT_PUBLIC_API_URL=http://localhost:8000
BACKEND_PORT=8000
FRONTEND_PORT=3000

# MCP Server
MCP_SERVER_NAME=tableau-analyst-agent
MCP_TRANSPORT=stdio  # or sse for web
MCP_LOG_LEVEL=info

# Model-to-Provider Mapping (Gateway)
MODEL_MAPPING='
{
  "gpt-4": {"provider": "openai", "auth": "direct"},
  "gpt-3.5-turbo": {"provider": "openai", "auth": "direct"},
  "claude-3-opus": {"provider": "anthropic", "auth": "direct"},
  "gemini-pro": {"provider": "vertex", "auth": "service_account"},
  "gemini-1.5-pro": {"provider": "vertex", "auth": "service_account"},
  "sfdc-xgen": {"provider": "salesforce", "auth": "jwt_oauth"},
  "einstein-gpt": {"provider": "salesforce", "auth": "jwt_oauth"}
}
'
```

## Docker Compose Configuration

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: tableau_demo
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  gateway:
    build:
      context: ./backend
      dockerfile: Dockerfile.gateway
    ports:
      - "8001:8001"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - SALESFORCE_CLIENT_ID=${SALESFORCE_CLIENT_ID}
      - SALESFORCE_PRIVATE_KEY_PATH=/app/credentials/salesforce-private-key.pem
      - VERTEX_PROJECT_ID=${VERTEX_PROJECT_ID}
      - VERTEX_SERVICE_ACCOUNT_PATH=/app/credentials/vertex-sa.json
    volumes:
      - ./credentials:/app/credentials:ro
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/gateway/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tableau_demo
      - REDIS_URL=redis://redis:6379/0
      - GATEWAY_BASE_URL=http://gateway:8001
      - TABLEAU_SERVER_URL=${TABLEAU_SERVER_URL}
      - TABLEAU_CLIENT_ID=${TABLEAU_CLIENT_ID}
      - TABLEAU_CLIENT_SECRET=${TABLEAU_CLIENT_SECRET}
    depends_on:
      - postgres
      - redis
      - gateway
    volumes:
      - ./backend:/app

  mcp-server:
    build:
      context: ./backend
      dockerfile: Dockerfile.mcp
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tableau_demo
      - GATEWAY_BASE_URL=http://gateway:8001
      - MCP_TRANSPORT=sse
    depends_on:
      - postgres
      - gateway

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  postgres_data:
  redis_data:
```

## Detailed Work Breakdown with Success Criteria

### Phase 1: Project Setup & Infrastructure

#### Task 1.1: Initialize Next.js Frontend
**Work Items:**
- [ ] Create Next.js app: `npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir`
- [ ] Install shadcn/ui: `npx shadcn-ui@latest init`
- [ ] Configure ESLint 9 in `eslint.config.js`
- [ ] Set up project structure (components/, lib/, types/)
- [ ] Configure `tsconfig.json` with strict mode
- [ ] Install dependencies: `axios`, `@tanstack/react-query`

**Success Criteria:**
- Next.js dev server runs on port 3000
- Tailwind CSS classes render correctly
- TypeScript compilation successful with strict mode
- ESLint 9 runs without errors
- Project structure matches plan

**Unit Tests:**
```bash
# Verify build
cd frontend && npm run build
# Verify linting
npm run lint
# Verify TypeScript
npx tsc --noEmit
```

#### Task 1.2: Initialize FastAPI Backend
**Work Items:**
- [ ] Create `backend/` directory structure
- [ ] Create `requirements.txt` with pinned versions
- [ ] Set up virtual environment: `python -m venv venv`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create FastAPI app in `app/main.py`
- [ ] Configure CORS middleware for frontend origin
- [ ] Set up pytest configuration
- [ ] Create `credentials/` directory with `.gitignore`

**Success Criteria:**
- FastAPI server runs on port 8000
- `/docs` endpoint accessible (Swagger UI)
- CORS configured for localhost:3000
- Health check endpoint returns 200
- pytest runs successfully
- Credentials directory exists and gitignored

**Unit Tests:**
```python
# tests/test_main.py
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_cors_headers(client):
    response = client.options("/")
    assert "access-control-allow-origin" in response.headers
```

#### Task 1.3: PostgreSQL & Redis Setup
**Work Items:**
- [ ] Create `docker-compose.yml` with PostgreSQL and Redis services
- [ ] Set up SQLAlchemy base models in `app/core/database.py`
- [ ] Set up Redis connection in `app/core/cache.py`
- [ ] Configure Alembic: `alembic init alembic`
- [ ] Create `.env.example` with database and Redis URLs
- [ ] Test database and Redis connections

**Success Criteria:**
- PostgreSQL container runs successfully
- Redis container runs successfully
- Database connection established
- Redis connection established
- Alembic can generate migrations
- Connection pooling configured
- Database and Redis health checks pass

**Unit Tests:**
```python
# tests/test_database.py
def test_database_connection():
    from app.core.database import engine
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        assert result.scalar() == 1

def test_session_creation():
    from app.core.database import get_db
    db = next(get_db())
    assert db is not None
    db.close()

# tests/test_cache.py
def test_redis_connection():
    from app.core.cache import redis_client
    assert redis_client.ping() is True

def test_redis_set_get():
    from app.core.cache import redis_client
    redis_client.set("test_key", "test_value", ex=60)
    assert redis_client.get("test_key") == b"test_value"
```

---

### Phase 2: Database Schema

#### Task 2.1: Chat History Models
**Work Items:**
- [ ] Create `app/models/chat.py` with Conversation model
- [ ] Create Message model with relationships
- [ ] Create Session model
- [ ] Add indexes on frequently queried fields
- [ ] Generate Alembic migration: `alembic revision --autogenerate -m "add chat models"`
- [ ] Apply migration: `alembic upgrade head`

**Success Criteria:**
- All models inherit from SQLAlchemy Base
- Foreign key relationships defined correctly
- Timestamps auto-populated (created_at, updated_at)
- Migration runs without errors
- Models can be queried via ORM

**Unit Tests:**
```python
# tests/test_chat_models.py
def test_create_conversation(db_session):
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    assert conv.id is not None
    assert conv.created_at is not None

def test_message_conversation_relationship(db_session):
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg = Message(conversation_id=conv.id, role="user", content="test")
    db_session.add(msg)
    db_session.commit()
    
    assert msg.conversation.id == conv.id
    assert len(conv.messages) == 1

def test_message_ordering(db_session):
    conv = Conversation()
    msg1 = Message(conversation=conv, role="user", content="first", created_at=datetime(2024,1,1))
    msg2 = Message(conversation=conv, role="assistant", content="second", created_at=datetime(2024,1,2))
    db_session.add_all([conv, msg1, msg2])
    db_session.commit()
    
    messages = conv.messages.order_by(Message.created_at).all()
    assert messages[0].content == "first"
    assert messages[1].content == "second"
```

#### Task 2.2: Tableau Metadata Cache (Optional)
**Work Items:**
- [ ] Create `app/models/tableau.py` with Datasource model
- [ ] Create View model with relationships
- [ ] Add cache invalidation logic
- [ ] Generate and apply migration

**Success Criteria:**
- Models can store Tableau metadata
- TTL mechanism for cache invalidation
- Query performance improved with cache

**Unit Tests:**
```python
# tests/test_tableau_models.py
def test_datasource_cache(db_session):
    ds = Datasource(tableau_id="ds-123", name="Sales Data", project="Finance")
    db_session.add(ds)
    db_session.commit()
    
    retrieved = db_session.query(Datasource).filter_by(tableau_id="ds-123").first()
    assert retrieved.name == "Sales Data"

def test_view_datasource_relationship(db_session):
    ds = Datasource(tableau_id="ds-123", name="Sales Data")
    view = View(tableau_id="v-456", name="Sales Dashboard", datasource=ds)
    db_session.add_all([ds, view])
    db_session.commit()
    
    assert view.datasource.tableau_id == "ds-123"
```

---

### Phase 3: Tableau Integration

#### Task 3.1: Tableau REST API Client
**Work Items:**
- [ ] Create `app/services/tableau/client.py` with TableauClient class
- [ ] Implement JWT authentication for Connected Apps
- [ ] Implement `sign_in()` method returning auth token
- [ ] Implement `get_datasources()` method
- [ ] Implement `get_views()` method
- [ ] Implement `query_datasource()` method
- [ ] Implement `get_view_embed_url()` method
- [ ] Add error handling and retries

**Success Criteria:**
- Authentication returns valid token
- All methods return properly typed responses
- Rate limiting handled gracefully
- Errors properly propagated
- Token refresh implemented

**Unit Tests:**
```python
# tests/test_tableau_client.py
@pytest.fixture
def mock_tableau_client():
    with patch('httpx.Client') as mock:
        yield mock

def test_sign_in(mock_tableau_client):
    client = TableauClient(server_url="https://test.com", client_id="123", client_secret="abc")
    client.sign_in()
    assert client.auth_token is not None

def test_get_datasources(mock_tableau_client):
    client = TableauClient(server_url="https://test.com", client_id="123", client_secret="abc")
    client.auth_token = "fake-token"
    
    mock_tableau_client.return_value.get.return_value.json.return_value = {
        "datasources": {"datasource": [{"id": "1", "name": "Test DS"}]}
    }
    
    datasources = client.get_datasources()
    assert len(datasources) == 1
    assert datasources[0]["name"] == "Test DS"

def test_query_datasource_with_filter(mock_tableau_client):
    client = TableauClient(server_url="https://test.com", client_id="123", client_secret="abc")
    client.auth_token = "fake-token"
    
    result = client.query_datasource("ds-123", filters={"year": "2024"})
    assert result is not None

def test_authentication_retry_on_401(mock_tableau_client):
    client = TableauClient(server_url="https://test.com", client_id="123", client_secret="abc")
    # Simulate 401 then success
    mock_response = Mock()
    mock_response.status_code = 401
    mock_tableau_client.return_value.get.side_effect = [mock_response, {"datasources": []}]
    
    datasources = client.get_datasources()
    assert client.sign_in.called
```

#### Task 3.2: Backend Tableau API Endpoints
**Work Items:**
- [ ] Create `app/api/tableau.py` with router
- [ ] Implement `GET /api/tableau/datasources`
- [ ] Implement `GET /api/tableau/views`
- [ ] Implement `POST /api/tableau/query`
- [ ] Implement `GET /api/tableau/views/{view_id}/embed-url`
- [ ] Add request/response Pydantic models
- [ ] Add OpenAPI documentation

**Success Criteria:**
- All endpoints return correct status codes
- Response schemas validated by Pydantic
- Swagger docs display correctly
- Error responses properly formatted
- Endpoints use dependency injection for TableauClient

**Unit Tests:**
```python
# tests/test_tableau_api.py
def test_list_datasources(client, mock_tableau_service):
    mock_tableau_service.get_datasources.return_value = [
        {"id": "ds-1", "name": "Sales"}
    ]
    
    response = client.get("/api/tableau/datasources")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Sales"

def test_list_views_filtered_by_datasource(client, mock_tableau_service):
    response = client.get("/api/tableau/views?datasource_id=ds-1")
    assert response.status_code == 200
    assert all(v["datasource_id"] == "ds-1" for v in response.json())

def test_query_datasource(client, mock_tableau_service):
    payload = {
        "datasource_id": "ds-1",
        "query": "SELECT * FROM sales WHERE year = 2024"
    }
    response = client.post("/api/tableau/query", json=payload)
    assert response.status_code == 200
    assert "data" in response.json()

def test_get_embed_url(client, mock_tableau_service):
    mock_tableau_service.get_view_embed_url.return_value = "https://tableau.com/embed/view-123?token=abc"
    
    response = client.get("/api/tableau/views/view-123/embed-url")
    assert response.status_code == 200
    assert "url" in response.json()
    assert "token" in response.json()["url"]

def test_datasources_unauthorized(client):
    # Test without auth
    response = client.get("/api/tableau/datasources")
    assert response.status_code == 401
```

#### Task 3.3: Frontend Tableau Components
**Work Items:**
- [ ] Create `components/tableau/ViewEmbedder.tsx`
- [ ] Install Tableau Embedding API v3: `npm install @tableau/embedding-api`
- [ ] Create `components/tableau/DataSourceList.tsx`
- [ ] Create `components/tableau/ViewList.tsx`
- [ ] Create `lib/tableau.ts` helper functions
- [ ] Add TypeScript types in `types/tableau.ts`

**Success Criteria:**
- ViewEmbedder successfully embeds Tableau views
- Responsive design works on mobile
- Loading states display correctly
- Error states handled gracefully
- Components properly typed

**Unit Tests:**
```typescript
// __tests__/tableau/ViewEmbedder.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import ViewEmbedder from '@/components/tableau/ViewEmbedder';

describe('ViewEmbedder', () => {
  test('renders loading state initially', () => {
    render(<ViewEmbedder viewId="view-123" />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  test('embeds view successfully', async () => {
    render(<ViewEmbedder viewId="view-123" embedUrl="https://test.com/embed" />);
    
    await waitFor(() => {
      expect(screen.getByTestId('tableau-viz')).toBeInTheDocument();
    });
  });

  test('displays error on failed embed', async () => {
    render(<ViewEmbedder viewId="invalid" />);
    
    await waitFor(() => {
      expect(screen.getByText(/error loading view/i)).toBeInTheDocument();
    });
  });
});

// __tests__/tableau/DataSourceList.test.tsx
describe('DataSourceList', () => {
  test('displays list of datasources', async () => {
    const datasources = [
      { id: 'ds-1', name: 'Sales Data' },
      { id: 'ds-2', name: 'Marketing Data' }
    ];
    
    render(<DataSourceList datasources={datasources} />);
    
    expect(screen.getByText('Sales Data')).toBeInTheDocument();
    expect(screen.getByText('Marketing Data')).toBeInTheDocument();
  });

  test('calls onSelect when datasource clicked', () => {
    const onSelect = jest.fn();
    const datasources = [{ id: 'ds-1', name: 'Sales Data' }];
    
    render(<DataSourceList datasources={datasources} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByText('Sales Data'));
    expect(onSelect).toHaveBeenCalledWith('ds-1');
  });
});
```

---

### Phase 4: AI Integration

#### Task 4.1: Gateway Router & Context Resolution
**Work Items:**
- [ ] Create `app/services/gateway/router.py` with main routing logic
- [ ] Implement `resolve_context()` function (model name → provider + auth strategy)
- [ ] Create model-to-provider mapping configuration
- [ ] Implement strategy pattern for provider selection
- [ ] Add gateway health check endpoint: `GET /gateway/health`

**Success Criteria:**
- Model names correctly map to providers (e.g., "gpt-4" → OpenAI, "gemini-pro" → Vertex)
- Context object contains provider, auth type, and credentials path
- Unknown models return clear error messages
- Configuration supports multiple models per provider

**Unit Tests:**
```python
# tests/test_gateway_router.py
from app.services.gateway.router import resolve_context, unified_llm_gateway

def test_resolve_context_openai():
    context = resolve_context("gpt-4")
    assert context.provider == "openai"
    assert context.auth_type == "direct"

def test_resolve_context_salesforce():
    context = resolve_context("sfdc-xgen")
    assert context.provider == "salesforce"
    assert context.auth_type == "jwt_oauth"
    assert context.requires_trust_header is True

def test_resolve_context_vertex():
    context = resolve_context("gemini-pro")
    assert context.provider == "vertex"
    assert context.auth_type == "service_account"

def test_resolve_context_unknown_model():
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_context("invalid-model")

@pytest.mark.asyncio
async def test_gateway_routing_flow():
    request = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    response = await unified_llm_gateway(request, auth_header="Bearer test-key")
    assert response["choices"][0]["message"]["content"] is not None
```

#### Task 4.2: Authentication Adapters
**Work Items:**
- [ ] Create `app/services/gateway/auth/direct.py` - API key passthrough
- [ ] Create `app/services/gateway/auth/salesforce.py` - JWT OAuth flow
- [ ] Create `app/services/gateway/auth/vertex.py` - Service account flow
- [ ] Implement Redis-based token caching in `app/services/gateway/cache.py`
- [ ] Add token expiration checking (5-min buffer before TTL)

**Success Criteria:**
- Direct auth passes API keys through unchanged
- Salesforce auth generates valid JWT and exchanges for OAuth token
- Vertex auth loads service account JSON and generates OAuth token
- Tokens cached in Redis with proper TTL
- Expired tokens automatically refreshed

**Unit Tests:**
```python
# tests/test_gateway_auth.py
from app.services.gateway.auth.direct import DirectAuthenticator
from app.services.gateway.auth.salesforce import SalesforceAuthenticator
from app.services.gateway.auth.vertex import VertexAuthenticator

@pytest.mark.asyncio
async def test_direct_auth():
    auth = DirectAuthenticator()
    token = await auth.get_token("Bearer sk-test123")
    assert token == "sk-test123"

@pytest.mark.asyncio
async def test_salesforce_jwt_flow(mock_sfdc_api):
    auth = SalesforceAuthenticator(
        client_id="test-id",
        private_key_path="./credentials/test-key.pem",
        username="test@example.com"
    )
    
    # Should generate JWT and exchange for bearer token
    token = await auth.get_token()
    assert token.startswith("00D")  # Salesforce token format
    
    # Verify token cached
    cached_token = await auth.get_token()
    assert cached_token == token

@pytest.mark.asyncio
async def test_vertex_service_account_flow(mock_gcp_api):
    auth = VertexAuthenticator(
        project_id="test-project",
        service_account_path="./credentials/vertex-sa.json"
    )
    
    token = await auth.get_token()
    assert token is not None
    
    # Verify token cached with TTL buffer
    import time
    time.sleep(1)
    cached_token = await auth.get_token()
    assert cached_token == token  # Should use cache

@pytest.mark.asyncio
async def test_token_cache_expiration(redis_client):
    from app.services.gateway.cache import TokenCache
    
    cache = TokenCache(redis_client)
    cache.set("test-key", "test-token", ttl=2)  # 2 second TTL
    
    assert cache.get("test-key") == "test-token"
    
    import time
    time.sleep(3)
    assert cache.get("test-key") is None  # Expired
```

#### Task 4.3: Request/Response Translators
**Work Items:**
- [ ] Create `app/services/gateway/translators/openai.py` - Passthrough
- [ ] Create `app/services/gateway/translators/salesforce.py` - Nested params + Trust Layer header
- [ ] Create `app/services/gateway/translators/vertex.py` - Convert to contents/parts format
- [ ] Implement response normalizer (all responses → OpenAI format)
- [ ] Handle streaming responses across all translators

**Success Criteria:**
- OpenAI requests pass through unchanged
- Salesforce requests have nested `parameters` object and `x-sfdc-app-context` header
- Vertex requests use `contents` array with `role` and `parts`
- All responses normalized to OpenAI `choices[0].message.content` format
- Streaming works across all providers

**Unit Tests:**
```python
# tests/test_gateway_translators.py
from app.services.gateway.translators.openai import OpenAITranslator
from app.services.gateway.translators.salesforce import SalesforceTranslator
from app.services.gateway.translators.vertex import VertexTranslator

def test_openai_translator_passthrough():
    translator = OpenAITranslator()
    request = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7
    }
    
    url, payload, headers = translator.transform_request(request)
    assert url == "https://api.openai.com/v1/chat/completions"
    assert payload == request  # Unchanged
    assert "x-sfdc-app-context" not in headers

def test_salesforce_translator_nested_params():
    translator = SalesforceTranslator()
    request = {
        "model": "sfdc-xgen",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.8,
        "top_p": 0.95
    }
    
    url, payload, headers = translator.transform_request(request)
    assert url.endswith("/models/sfdc-xgen/chat-generations")
    assert "parameters" in payload
    assert payload["parameters"]["temperature"] == 0.8
    assert payload["parameters"]["top_p"] == 0.95
    assert headers["x-sfdc-app-context"] == "EinsteinGPT"

def test_vertex_translator_contents_format():
    translator = VertexTranslator()
    request = {
        "model": "gemini-pro",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    url, payload, headers = translator.transform_request(request)
    assert "contents" in payload
    assert len(payload["contents"]) == 3
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == "Hello"
    assert payload["contents"][1]["role"] == "model"  # assistant → model
    assert payload["generationConfig"]["temperature"] == 0.7
    assert payload["generationConfig"]["maxOutputTokens"] == 1024

def test_response_normalizer_openai():
    from app.services.gateway.translators import normalize_response
    
    openai_response = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"total_tokens": 50}
    }
    
    normalized = normalize_response(openai_response, "openai")
    assert normalized["choices"][0]["message"]["content"] == "Hello"

def test_response_normalizer_vertex():
    from app.services.gateway.translators import normalize_response
    
    vertex_response = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Hello from Gemini"}]
            }
        }],
        "usageMetadata": {"totalTokenCount": 45}
    }
    
    normalized = normalize_response(vertex_response, "vertex")
    assert normalized["choices"][0]["message"]["content"] == "Hello from Gemini"
    assert normalized["usage"]["total_tokens"] == 45

def test_response_normalizer_salesforce():
    from app.services.gateway.translators import normalize_response
    
    sfdc_response = {
        "choices": [{"message": {"content": "Hello from Einstein"}}],
        "usage": {"totalTokens": 60}
    }
    
    normalized = normalize_response(sfdc_response, "salesforce")
    assert normalized["choices"][0]["message"]["content"] == "Hello from Einstein"
```

#### Task 4.4: Unified AI Client
**Work Items:**
- [ ] Create `app/services/ai/client.py` - Single client that talks to gateway
- [ ] Implement `chat()` method using OpenAI-compatible interface
- [ ] Implement `stream_chat()` for streaming responses
- [ ] Add function calling support
- [ ] Implement error handling and retries
- [ ] Add token usage tracking

**Success Criteria:**
- Client sends requests to gateway (not directly to providers)
- All requests use OpenAI format regardless of backend provider
- Function calling works across all providers
- Streaming works across all providers
- Errors properly handled and logged

**Unit Tests:**
```python
# tests/test_ai_client.py
from app.services.ai.client import UnifiedAIClient

@pytest.fixture
def ai_client(mock_gateway):
    return UnifiedAIClient(gateway_url="http://localhost:8001")

@pytest.mark.asyncio
async def test_chat_via_gateway(ai_client, mock_gateway):
    mock_gateway.post("/v1/chat/completions").return_value = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"total_tokens": 20}
    }
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    )
    
    assert response.content == "Hello"
    assert response.tokens_used == 20

@pytest.mark.asyncio
async def test_stream_chat(ai_client, mock_gateway):
    mock_gateway.post("/v1/chat/completions").stream([
        'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
        'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
        'data: [DONE]\n\n'
    ])
    
    chunks = []
    async for chunk in ai_client.stream_chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}]
    ):
        chunks.append(chunk.content)
    
    assert chunks == ["Hello", " world"]

@pytest.mark.asyncio
async def test_function_calling_via_gateway(ai_client, mock_gateway):
    mock_gateway.post("/v1/chat/completions").return_value = {
        "choices": [{
            "message": {
                "function_call": {
                    "name": "list_datasources",
                    "arguments": "{}"
                }
            }
        }]
    }
    
    response = await ai_client.chat(
        model="gpt-4",
        messages=[{"role": "user", "content": "List datasources"}],
        functions=[{"name": "list_datasources", "parameters": {}}]
    )
    
    assert response.function_call.name == "list_datasources"

@pytest.mark.asyncio
async def test_cross_provider_consistency(ai_client, mock_gateway):
    """Test that all providers return consistent format"""
    models = ["gpt-4", "gemini-pro", "sfdc-xgen", "claude-3"]
    
    for model in models:
        mock_gateway.post("/v1/chat/completions").return_value = {
            "choices": [{"message": {"content": f"Response from {model}"}}]
        }
        
        response = await ai_client.chat(
            model=model,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        assert response.content == f"Response from {model}"
        assert response.model == model
```

#### Task 4.5: Gateway Deployment & Configuration
**Work Items:**
- [ ] Create gateway deployment configuration
- [ ] Set up model-to-provider mappings in config file
- [ ] Configure credential loading (env vars, secret manager)
- [ ] Set up Redis for token caching
- [ ] Create gateway Docker container
- [ ] Add gateway to docker-compose.yml

**Success Criteria:**
- Gateway runs as separate service (port 8001)
- All providers configurable via environment variables
- Credentials loaded securely (not hardcoded)
- Redis connection established
- Gateway accessible from backend service

**Unit Tests:**
```bash
# Test gateway deployment
docker-compose up -d gateway redis

# Test gateway health
curl http://localhost:8001/gateway/health
# Expected: {"status": "healthy", "providers": ["openai", "salesforce", "vertex", "anthropic"]}

# Test OpenAI-compatible interface
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Test Redis cache
redis-cli GET "token:salesforce:test-client-id"
```

---

### Phase 5: Chat Interface

#### Task 5.1: Backend Chat API
**Work Items:**
- [ ] Create `app/api/chat.py` with router
- [ ] Implement `POST /api/chat/message`
- [ ] Implement `GET /api/chat/conversations`
- [ ] Implement `GET /api/chat/conversations/{id}/messages`
- [ ] Implement `POST /api/chat/conversations`
- [ ] Add WebSocket endpoint for streaming
- [ ] Save messages to database

**Success Criteria:**
- Messages persist in database
- Conversation history retrievable
- Streaming works via WebSocket
- All endpoints properly documented
- Error handling complete

**Unit Tests:**
```python
# tests/test_chat_api.py
def test_create_conversation(client):
    response = client.post("/api/chat/conversations")
    assert response.status_code == 201
    assert "id" in response.json()
    assert "created_at" in response.json()

def test_send_message(client, db_session):
    # Create conversation first
    conv_response = client.post("/api/chat/conversations")
    conv_id = conv_response.json()["id"]
    
    # Send message
    payload = {
        "conversation_id": conv_id,
        "content": "List all datasources",
        "model": "gpt-4"
    }
    response = client.post("/api/chat/message", json=payload)
    
    assert response.status_code == 200
    assert "content" in response.json()
    assert "model" in response.json()
    
    # Verify message saved to DB
    messages = db_session.query(Message).filter_by(conversation_id=conv_id).all()
    assert len(messages) == 2  # User message + AI response

def test_get_conversation_history(client, db_session):
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg1 = Message(conversation_id=conv.id, role="user", content="Hello")
    msg2 = Message(conversation_id=conv.id, role="assistant", content="Hi there")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    response = client.get(f"/api/chat/conversations/{conv.id}/messages")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_list_conversations(client, db_session):
    conv1 = Conversation()
    conv2 = Conversation()
    db_session.add_all([conv1, conv2])
    db_session.commit()
    
    response = client.get("/api/chat/conversations")
    assert response.status_code == 200
    assert len(response.json()) >= 2
```

#### Task 5.2: Frontend Chat Components
**Work Items:**
- [ ] Create `components/chat/ChatInterface.tsx`
- [ ] Create `components/chat/MessageList.tsx`
- [ ] Create `components/chat/MessageInput.tsx`
- [ ] Create `components/chat/ModelSelector.tsx`
- [ ] Add markdown rendering for messages
- [ ] Add syntax highlighting for code blocks
- [ ] Implement auto-scroll to bottom

**Success Criteria:**
- Messages display in correct order
- User can send messages
- AI responses appear in real-time
- Markdown renders correctly
- Model selector works

**Unit Tests:**
```typescript
// __tests__/chat/MessageInput.test.tsx
describe('MessageInput', () => {
  test('calls onSend when message submitted', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);
    
    const input = screen.getByPlaceholderText(/type a message/i);
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.submit(input.closest('form')!);
    
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  test('clears input after send', () => {
    render(<MessageInput onSend={jest.fn()} />);
    
    const input = screen.getByPlaceholderText(/type a message/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.submit(input.closest('form')!);
    
    expect(input.value).toBe('');
  });

  test('disables send button when input empty', () => {
    render(<MessageInput onSend={jest.fn()} />);
    
    const button = screen.getByRole('button', { name: /send/i });
    expect(button).toBeDisabled();
  });
});

// __tests__/chat/MessageList.test.tsx
describe('MessageList', () => {
  test('renders list of messages', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Hello' },
      { id: '2', role: 'assistant', content: 'Hi there' }
    ];
    
    render(<MessageList messages={messages} />);
    
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there')).toBeInTheDocument();
  });

  test('auto-scrolls to bottom on new message', () => {
    const { rerender } = render(<MessageList messages={[]} />);
    const scrollSpy = jest.spyOn(Element.prototype, 'scrollIntoView');
    
    rerender(<MessageList messages={[{ id: '1', role: 'user', content: 'New' }]} />);
    
    expect(scrollSpy).toHaveBeenCalled();
  });
});

// __tests__/chat/ModelSelector.test.tsx
describe('ModelSelector', () => {
  test('displays available models', () => {
    const models = ['gpt-4', 'gemini-pro', 'claude-3'];
    render(<ModelSelector models={models} selected="gpt-4" onSelect={jest.fn()} />);
    
    fireEvent.click(screen.getByRole('button'));
    
    models.forEach(model => {
      expect(screen.getByText(model)).toBeInTheDocument();
    });
  });

  test('calls onSelect when model changed', () => {
    const onSelect = jest.fn();
    render(<ModelSelector models={['gpt-4', 'gemini-pro']} selected="gpt-4" onSelect={onSelect} />);
    
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('gemini-pro'));
    
    expect(onSelect).toHaveBeenCalledWith('gemini-pro');
  });
});
```

---

### Phase 6: MCP Server Implementation

#### Task 6.1: MCP Server Setup
**Work Items:**
- [ ] Install FastMCP: `pip install fastmcp`
- [ ] Create `mcp_server/server.py` with FastMCP initialization
- [ ] Configure stdio transport for IDE integration
- [ ] Configure SSE transport for web integration
- [ ] Set up connection lifecycle management
- [ ] Create MCP server configuration file

**Success Criteria:**
- MCP server starts successfully
- stdio transport accepts connections from Cursor/VS Code
- SSE transport accessible via HTTP
- Server responds to MCP protocol handshake
- Logging configured and working

**Unit Tests:**
```python
# tests/test_mcp_server.py
import pytest
from mcp_server.server import create_server

def test_server_initialization():
    server = create_server()
    assert server is not None
    assert server.name == "tableau-analyst-agent"

def test_stdio_transport():
    server = create_server(transport="stdio")
    assert server.transport == "stdio"
    # Test that server can read from stdin and write to stdout

def test_sse_transport():
    server = create_server(transport="sse")
    assert server.transport == "sse"
    # Test that server exposes HTTP endpoint

@pytest.mark.asyncio
async def test_server_lifecycle():
    server = create_server()
    await server.start()
    assert server.is_running
    await server.stop()
    assert not server.is_running
```

#### Task 6.2: MCP Tableau Tools
**Work Items:**
- [ ] Create `mcp_server/tools/tableau_tools.py`
- [ ] Implement `tableau_list_datasources` tool with JSON Schema
- [ ] Implement `tableau_list_views` tool with optional filters
- [ ] Implement `tableau_query_datasource` tool with query parameters
- [ ] Implement `tableau_get_view_embed_url` tool
- [ ] Register tools with MCP server
- [ ] Add tool documentation and examples

**Success Criteria:**
- All tools registered and discoverable via MCP
- Tools accept parameters according to JSON Schema
- Tools return properly formatted responses
- Error handling returns MCP-compliant errors
- Tools can be invoked from IDE (Cursor/VS Code)

**Unit Tests:**
```python
# tests/test_tableau_tools.py
from mcp_server.tools.tableau_tools import (
    tableau_list_datasources,
    tableau_list_views,
    tableau_query_datasource,
    tableau_get_view_embed_url
)

@pytest.mark.asyncio
async def test_list_datasources_tool(mock_tableau_client):
    result = await tableau_list_datasources()
    assert "datasources" in result
    assert isinstance(result["datasources"], list)

@pytest.mark.asyncio
async def test_list_views_tool_with_filter(mock_tableau_client):
    result = await tableau_list_views(datasource_id="ds-123")
    assert all(v["datasource_id"] == "ds-123" for v in result["views"])

@pytest.mark.asyncio
async def test_query_datasource_tool(mock_tableau_client):
    result = await tableau_query_datasource(
        datasource_id="ds-123",
        filters={"year": "2024", "region": "West"}
    )
    assert "data" in result
    assert "columns" in result
    assert "row_count" in result

@pytest.mark.asyncio
async def test_get_embed_url_tool(mock_tableau_client):
    result = await tableau_get_view_embed_url(view_id="view-123")
    assert "url" in result
    assert "token" in result["url"]
    assert result["url"].startswith("https://")

def test_tool_schemas():
    # Verify all tools have valid JSON schemas
    from mcp_server.server import get_registered_tools
    tools = get_registered_tools()
    
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
```

#### Task 6.3: MCP Conversation Tools
**Work Items:**
- [ ] Create `mcp_server/tools/chat_tools.py`
- [ ] Implement `chat_create_conversation` tool
- [ ] Implement `chat_get_conversation` tool
- [ ] Implement `chat_list_conversations` tool
- [ ] Implement `chat_add_message` tool
- [ ] Implement `chat_get_messages` tool with pagination
- [ ] Integrate with database models

**Success Criteria:**
- Conversation lifecycle managed via MCP tools
- Messages persist to database
- Tools accessible from both IDE and web
- Pagination works for long conversations
- Concurrent conversation handling works

**Unit Tests:**
```python
# tests/test_chat_tools.py
from mcp_server.tools.chat_tools import (
    chat_create_conversation,
    chat_get_conversation,
    chat_list_conversations,
    chat_add_message,
    chat_get_messages
)

@pytest.mark.asyncio
async def test_create_conversation(db_session):
    result = await chat_create_conversation()
    assert "conversation_id" in result
    assert "created_at" in result

@pytest.mark.asyncio
async def test_add_message_to_conversation(db_session):
    conv_result = await chat_create_conversation()
    conv_id = conv_result["conversation_id"]
    
    msg_result = await chat_add_message(
        conversation_id=conv_id,
        role="user",
        content="List datasources",
        model="gpt-4"
    )
    
    assert msg_result["message_id"] is not None
    assert msg_result["conversation_id"] == conv_id

@pytest.mark.asyncio
async def test_get_conversation_messages(db_session):
    conv_result = await chat_create_conversation()
    conv_id = conv_result["conversation_id"]
    
    await chat_add_message(conv_id, "user", "Hello")
    await chat_add_message(conv_id, "assistant", "Hi there")
    
    messages = await chat_get_messages(conversation_id=conv_id)
    assert len(messages["messages"]) == 2
    assert messages["messages"][0]["role"] == "user"
    assert messages["messages"][1]["role"] == "assistant"

@pytest.mark.asyncio
async def test_list_conversations_pagination(db_session):
    # Create multiple conversations
    for _ in range(15):
        await chat_create_conversation()
    
    result = await chat_list_conversations(limit=10, offset=0)
    assert len(result["conversations"]) == 10
    assert result["total"] >= 15
    
    result_page2 = await chat_list_conversations(limit=10, offset=10)
    assert len(result_page2["conversations"]) >= 5
```

#### Task 6.4: MCP Authentication Tools
**Work Items:**
- [ ] Create `mcp_server/tools/auth_tools.py`
- [ ] Implement `auth_tableau_signin` tool with JWT Connected App
- [ ] Implement `auth_get_token` tool (returns current token)
- [ ] Implement `auth_refresh_token` tool
- [ ] Implement secure credential storage (keyring or encrypted)
- [ ] Add token expiration handling

**Success Criteria:**
- Authentication works with Tableau Connected Apps
- Tokens stored securely (not in plaintext)
- Token refresh automatic before expiration
- Auth tools accessible via MCP
- RLS enforced via JWT tokens

**Unit Tests:**
```python
# tests/test_auth_tools.py
from mcp_server.tools.auth_tools import (
    auth_tableau_signin,
    auth_get_token,
    auth_refresh_token
)

@pytest.mark.asyncio
async def test_tableau_signin(mock_tableau_api):
    result = await auth_tableau_signin(
        server_url="https://tableau.example.com",
        client_id="test-client-id",
        client_secret="test-secret"
    )
    
    assert "token" in result
    assert "expires_at" in result
    assert result["authenticated"] is True

@pytest.mark.asyncio
async def test_get_current_token():
    # Sign in first
    await auth_tableau_signin("https://tableau.example.com", "id", "secret")
    
    result = await auth_get_token()
    assert result["token"] is not None
    assert result["expires_at"] is not None

@pytest.mark.asyncio
async def test_token_refresh(mock_tableau_api):
    # Sign in with token that expires soon
    await auth_tableau_signin("https://tableau.example.com", "id", "secret")
    
    result = await auth_refresh_token()
    assert result["token"] is not None
    assert result["refreshed"] is True

@pytest.mark.asyncio
async def test_credential_storage_security():
    from mcp_server.tools.auth_tools import CredentialStore
    
    store = CredentialStore()
    store.save_credentials("tableau", "client-id", "secret-key")
    
    # Verify credentials not stored in plaintext
    creds = store.get_credentials("tableau")
    assert creds["client_id"] == "client-id"
    assert creds["client_secret"] == "secret-key"
    
    # Verify storage is encrypted
    raw_storage = store._read_raw_storage()
    assert "secret-key" not in raw_storage  # Not plaintext
```

#### Task 6.5: MCP Resources
**Work Items:**
- [ ] Create `mcp_server/resources/conversation.py`
- [ ] Implement `conversation://{id}` resource
- [ ] Implement `datasources://list` resource
- [ ] Implement `views://list` resource
- [ ] Add resource caching with TTL
- [ ] Register resources with MCP server

**Success Criteria:**
- Resources accessible via MCP resource protocol
- Conversation history readable as resource
- Datasource/view lists cached appropriately
- Resources support MCP resource templates
- Resources update when underlying data changes

**Unit Tests:**
```python
# tests/test_mcp_resources.py
from mcp_server.resources.conversation import (
    ConversationResource,
    DatasourceListResource,
    ViewListResource
)

@pytest.mark.asyncio
async def test_conversation_resource(db_session):
    # Create conversation with messages
    conv = Conversation()
    db_session.add(conv)
    db_session.commit()
    
    msg1 = Message(conversation_id=conv.id, role="user", content="Hello")
    msg2 = Message(conversation_id=conv.id, role="assistant", content="Hi")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    # Access as MCP resource
    resource = ConversationResource()
    content = await resource.read(uri=f"conversation://{conv.id}")
    
    assert "messages" in content
    assert len(content["messages"]) == 2

@pytest.mark.asyncio
async def test_datasource_list_resource(mock_tableau_client):
    resource = DatasourceListResource()
    content = await resource.read(uri="datasources://list")
    
    assert "datasources" in content
    assert isinstance(content["datasources"], list)

@pytest.mark.asyncio
async def test_resource_caching():
    resource = DatasourceListResource()
    
    # First read
    content1 = await resource.read(uri="datasources://list")
    
    # Second read should use cache
    content2 = await resource.read(uri="datasources://list")
    
    assert content1 == content2
    assert resource.cache_hit_count == 1

@pytest.mark.asyncio
async def test_resource_cache_expiration():
    import time
    resource = DatasourceListResource(ttl=1)  # 1 second TTL
    
    # First read
    await resource.read(uri="datasources://list")
    
    # Wait for cache to expire
    time.sleep(2)
    
    # Second read should fetch fresh data
    await resource.read(uri="datasources://list")
    assert resource.cache_miss_count == 2
```

#### Task 6.6: MCP IDE Integration
**Work Items:**
- [ ] Create `mcp-config.json` for Cursor/VS Code
- [ ] Document stdio connection setup
- [ ] Create example IDE workflow
- [ ] Test tool invocation from IDE
- [ ] Create keyboard shortcuts documentation

**Success Criteria:**
- MCP server connectable from Cursor
- MCP server connectable from VS Code
- Tools discoverable in IDE
- Tool invocations work from IDE
- Documentation complete

**Unit Tests:**
```bash
# Manual testing checklist for IDE integration

# 1. Configure Cursor
# Add to ~/.cursor/mcp-config.json:
{
  "tableau-analyst-agent": {
    "command": "python",
    "args": ["/path/to/mcp_server/server.py"],
    "transport": "stdio"
  }
}

# 2. Test connection
# In Cursor, open MCP panel and verify server appears

# 3. Test tool discovery
# Verify these tools appear:
# - tableau_list_datasources
# - tableau_list_views
# - tableau_query_datasource
# - tableau_get_view_embed_url
# - chat_create_conversation
# - chat_add_message
# - auth_tableau_signin

# 4. Test tool invocation
# Call tableau_list_datasources from IDE
# Verify response appears correctly

# 5. Test resource access
# Access conversation://123
# Verify conversation history displays
```

#### Task 6.7: MCP Web Integration (SSE)
**Work Items:**
- [ ] Create SSE endpoint in FastAPI: `GET /mcp/sse`
- [ ] Configure MCP server for SSE transport
- [ ] Add CORS headers for SSE
- [ ] Implement connection pooling
- [ ] Add heartbeat mechanism

**Success Criteria:**
- SSE endpoint accessible from frontend
- MCP tools callable via SSE
- Connection stays alive with heartbeat
- Multiple concurrent SSE connections work
- Graceful disconnect handling

**Unit Tests:**
```python
# tests/test_mcp_sse.py
import pytest
from fastapi.testclient import TestClient

def test_sse_endpoint_exists(client):
    response = client.get("/mcp/sse")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"

@pytest.mark.asyncio
async def test_sse_tool_invocation(sse_client):
    # Connect to SSE endpoint
    async with sse_client.stream("/mcp/sse") as stream:
        # Send tool invocation
        await sse_client.post("/mcp/sse/invoke", json={
            "tool": "tableau_list_datasources",
            "arguments": {}
        })
        
        # Read response from stream
        async for event in stream:
            if event.event == "tool_result":
                result = json.loads(event.data)
                assert "datasources" in result
                break

def test_sse_heartbeat(sse_client):
    # Connect and wait for heartbeat
    with sse_client.stream("/mcp/sse") as stream:
        events = []
        for event in stream:
            events.append(event)
            if event.event == "heartbeat":
                break
        
        assert any(e.event == "heartbeat" for e in events)

def test_sse_cors_headers(client):
    response = client.options("/mcp/sse")
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
```

---

### Phase 7: Agentic Capabilities

#### Task 7.1: Function Calling / Tool Use
**Work Items:**
- [ ] Define tools in `app/services/ai/tools.py`
- [ ] Implement `list_datasources_tool`
- [ ] Implement `list_views_tool`
- [ ] Implement `query_datasource_tool`
- [ ] Implement `embed_view_tool`
- [ ] Create tool executor
- [ ] Add tool result formatting

**Success Criteria:**
- Tools properly defined with JSON schemas
- AI can call tools based on user intent
- Tool results formatted for display
- Multi-step tool execution works

**Unit Tests:**
```python
# tests/test_tools.py
def test_list_datasources_tool(tableau_client):
    from app.services.ai.tools import list_datasources_tool
    
    result = list_datasources_tool()
    assert isinstance(result, list)
    assert all("id" in ds and "name" in ds for ds in result)

def test_query_datasource_tool(tableau_client):
    from app.services.ai.tools import query_datasource_tool
    
    result = query_datasource_tool(datasource_id="ds-123", filters={"year": "2024"})
    assert "data" in result
    assert isinstance(result["data"], list)

def test_tool_executor():
    from app.services.ai.tools import execute_tool
    
    result = execute_tool("list_datasources", {})
    assert result["status"] == "success"
    assert "data" in result

def test_tool_error_handling():
    from app.services.ai.tools import execute_tool
    
    result = execute_tool("query_datasource", {"datasource_id": "invalid"})
    assert result["status"] == "error"
    assert "message" in result
```

#### Task 7.2: Intent Recognition & Multi-Step Planning
**Work Items:**
- [ ] Create `app/services/ai/agent.py` with Agent class
- [ ] Implement intent classification
- [ ] Implement multi-step planning
- [ ] Add conversation context management
- [ ] Implement tool selection logic

**Success Criteria:**
- Agent correctly identifies user intent
- Plans multi-step actions when needed
- Maintains conversation context
- Handles ambiguous queries

**Unit Tests:**
```python
# tests/test_agent.py
def test_intent_classification():
    from app.services.ai.agent import Agent
    
    agent = Agent()
    
    intent = agent.classify_intent("Show me all datasources")
    assert intent == "list_datasources"
    
    intent = agent.classify_intent("What's the total sales in 2024?")
    assert intent == "query_datasource"

def test_multi_step_planning():
    from app.services.ai.agent import Agent
    
    agent = Agent()
    plan = agent.create_plan("Show me a chart of sales by region for 2024")
    
    assert len(plan) >= 2
    assert plan[0]["action"] == "query_datasource"
    assert plan[1]["action"] == "embed_view"

def test_conversation_context():
    from app.services.ai.agent import Agent
    
    agent = Agent()
    agent.add_message("user", "Show me sales data")
    agent.add_message("assistant", "Here are the datasources...")
    agent.add_message("user", "Query the first one")
    
    context = agent.get_context()
    assert len(context) == 3
    assert agent.can_resolve_reference("the first one")
```

---

### Phase 8: UI/UX Polish

#### Task 8.1: Responsive Design & Styling
**Work Items:**
- [ ] Implement mobile-responsive layout
- [ ] Add dark mode support using Tailwind
- [ ] Create loading skeletons
- [ ] Design error states
- [ ] Create empty states
- [ ] Add animations/transitions

**Success Criteria:**
- Works on mobile (320px width)
- Works on tablet (768px width)
- Works on desktop (1920px width)
- Dark mode toggles correctly
- Loading states show immediately

**Unit Tests:**
```typescript
// __tests__/responsive.test.tsx
describe('Responsive Design', () => {
  test('mobile layout renders correctly', () => {
    global.innerWidth = 375;
    render(<ChatInterface />);
    // Verify mobile-specific layout
  });

  test('desktop layout renders correctly', () => {
    global.innerWidth = 1920;
    render(<ChatInterface />);
    // Verify desktop-specific layout
  });
});

// __tests__/dark-mode.test.tsx
describe('Dark Mode', () => {
  test('toggles between light and dark', () => {
    render(<App />);
    const toggle = screen.getByLabelText(/toggle dark mode/i);
    
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
```

---

### Phase 9: Testing & Deployment

#### Task 9.1: Integration Tests
**Work Items:**
- [ ] Create `tests/integration/test_chat_flow.py`
- [ ] Test complete chat conversation flow
- [ ] Test Tableau integration end-to-end
- [ ] Test AI provider fallback
- [ ] Test error recovery

**Success Criteria:**
- All integration tests pass
- Tests cover happy path and error cases
- Tests run in CI/CD pipeline

**Unit Tests:**
```python
# tests/integration/test_chat_flow.py
def test_complete_chat_flow(client, db_session):
    # Create conversation
    conv_response = client.post("/api/chat/conversations")
    conv_id = conv_response.json()["id"]
    
    # User asks to list datasources
    msg1 = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "content": "List all datasources",
        "model": "gpt-4"
    })
    assert "datasource" in msg1.json()["content"].lower()
    
    # User asks to query a datasource
    msg2 = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "content": "Query the sales datasource for 2024 data",
        "model": "gpt-4"
    })
    assert msg2.status_code == 200
    
    # Verify conversation history
    history = client.get(f"/api/chat/conversations/{conv_id}/messages")
    assert len(history.json()) >= 4  # 2 user + 2 assistant messages
```

#### Task 9.2: MCP Server Integration Tests
**Work Items:**
- [ ] Test end-to-end MCP tool invocation from IDE
- [ ] Test MCP tool invocation from web (SSE)
- [ ] Test conversation flow via MCP
- [ ] Test authentication flow via MCP
- [ ] Test resource access patterns
- [ ] Load test MCP server with concurrent connections

**Success Criteria:**
- IDE can complete full workflow via MCP
- Web can complete full workflow via MCP
- Concurrent connections handled correctly
- No memory leaks under load
- Error handling works across MCP boundary

**Unit Tests:**
```python
# tests/integration/test_mcp_flow.py
@pytest.mark.asyncio
async def test_complete_mcp_workflow_from_ide():
    """Test complete workflow: auth -> list datasources -> query -> get results"""
    # 1. Authenticate
    auth_result = await call_mcp_tool("auth_tableau_signin", {
        "server_url": "https://tableau.test.com",
        "client_id": "test-id",
        "client_secret": "test-secret"
    })
    assert auth_result["authenticated"]
    
    # 2. List datasources
    ds_result = await call_mcp_tool("tableau_list_datasources", {})
    assert len(ds_result["datasources"]) > 0
    
    # 3. Query first datasource
    ds_id = ds_result["datasources"][0]["id"]
    query_result = await call_mcp_tool("tableau_query_datasource", {
        "datasource_id": ds_id,
        "filters": {"year": "2024"}
    })
    assert "data" in query_result

@pytest.mark.asyncio
async def test_mcp_conversation_via_sse():
    """Test conversation management via SSE transport"""
    async with SSEClient("/mcp/sse") as client:
        # Create conversation
        conv = await client.call_tool("chat_create_conversation", {})
        conv_id = conv["conversation_id"]
        
        # Add messages
        await client.call_tool("chat_add_message", {
            "conversation_id": conv_id,
            "role": "user",
            "content": "Show me sales data"
        })
        
        # Retrieve conversation as resource
        resource = await client.read_resource(f"conversation://{conv_id}")
        assert len(resource["messages"]) == 1

@pytest.mark.asyncio
async def test_mcp_load_handling():
    """Test MCP server under load"""
    async with asyncio.TaskGroup() as tg:
        tasks = []
        for i in range(50):
            task = tg.create_task(
                call_mcp_tool("tableau_list_datasources", {})
            )
            tasks.append(task)
        
        results = [task.result() for task in tasks]
        assert all("datasources" in r for r in results)
```

#### Task 9.3: Docker & Deployment
**Work Items:**
- [ ] Create `backend/Dockerfile`
- [ ] Create `frontend/Dockerfile`
- [ ] Create `mcp_server/Dockerfile`
- [ ] Update `docker-compose.yml` with all services (FastAPI, Frontend, PostgreSQL, MCP Server)
- [ ] Add health checks to containers
- [ ] Create CI/CD pipeline (GitHub Actions)
- [ ] Write deployment documentation
- [ ] Document MCP server deployment (stdio vs SSE)

**Success Criteria:**
- `docker-compose up` starts all services
- Health checks pass
- Environment variables properly injected
- CI/CD runs tests and builds images

**Unit Tests:**
```bash
# Test Docker builds
docker build -t tableau-demo-backend backend/
docker build -t tableau-demo-frontend frontend/
docker build -t tableau-demo-gateway backend/ -f backend/Dockerfile.gateway
docker build -t tableau-demo-mcp backend/ -f backend/Dockerfile.mcp

# Test docker-compose
docker-compose up -d
docker-compose ps | grep "Up"

# Test health endpoints
curl http://localhost:8000/health  # Backend
curl http://localhost:3000  # Frontend
curl http://localhost:8001/gateway/health  # Gateway
curl http://localhost:8002/health  # MCP server

# Test database connectivity
docker-compose exec backend python -c "from app.core.database import engine; engine.connect()"

# Test Redis connectivity
docker-compose exec backend python -c "from app.core.cache import redis_client; print(redis_client.ping())"

# Test gateway routing
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'

# Test MCP server
docker-compose exec mcp-server python -c "from mcp_server.server import create_server; server = create_server(); print('MCP OK')"

# Test MCP SSE endpoint
curl http://localhost:8002/mcp/sse
```

---

### Phase 10: VizQL Agent & Summary Agent ⭐

#### Task 10.1: VizQL Agent Implementation
**Work Items:**
- [ ] Create `app/services/agents/vds_agent.py`
- [ ] Implement VizQL query construction logic
- [ ] Create datasource schema introspection
- [ ] Add natural language to VizQL translation
- [ ] Implement query validation
- [ ] Add query optimization heuristics

**Success Criteria:**
- Agent correctly interprets user questions
- Generates valid VizQL queries
- Handles datasource context
- Validates query syntax before execution
- Optimizes queries for performance

**Unit Tests:**
```python
# tests/test_vds_agent.py
def test_vds_agent_query_construction():
    agent = VDSAgent()
    
    result = agent.construct_query(
        user_query="Show me total sales by region for 2024",
        datasource_context={
            "id": "ds-123",
            "columns": ["sales", "region", "date"],
            "schema": {...}
        }
    )
    
    assert "SELECT" in result["vizql"]
    assert "SUM(sales)" in result["vizql"]
    assert "GROUP BY region" in result["vizql"]
    assert result["valid"] is True

def test_vds_agent_schema_understanding():
    agent = VDSAgent()
    
    schema = agent.analyze_datasource("ds-123")
    
    assert "columns" in schema
    assert "measures" in schema
    assert "dimensions" in schema
    assert "calculated_fields" in schema

def test_vds_agent_query_validation():
    agent = VDSAgent()
    
    # Valid query
    assert agent.validate_query("SELECT SUM([Sales]) FROM datasource") is True
    
    # Invalid query
    assert agent.validate_query("INVALID SYNTAX") is False
```

#### Task 10.2: VizQL MCP Tools
**Work Items:**
- [ ] Create `mcp_server/tools/vizql_tools.py`
- [ ] Implement `tableau_construct_vizql` tool
- [ ] Implement `tableau_execute_vizql` tool
- [ ] Implement `tableau_get_datasource_schema` tool
- [ ] Implement `tableau_validate_vizql` tool
- [ ] Add error handling for VizQL syntax errors

**Success Criteria:**
- Tools expose VizQL capabilities via MCP
- Schema introspection works for all datasources
- VizQL execution returns structured results
- Validation catches syntax errors before execution

**Unit Tests:**
```python
# tests/test_vizql_tools.py
@pytest.mark.asyncio
async def test_construct_vizql_tool():
    result = await tableau_construct_vizql(
        user_query="Total sales by region",
        datasource_id="ds-123"
    )
    
    assert "vizql" in result
    assert "explanation" in result
    assert result["valid"] is True

@pytest.mark.asyncio
async def test_execute_vizql_tool():
    result = await tableau_execute_vizql(
        datasource_id="ds-123",
        vizql_query="SELECT SUM([Sales]) AS total_sales FROM datasource"
    )
    
    assert "data" in result
    assert "columns" in result
    assert result["row_count"] > 0

@pytest.mark.asyncio
async def test_get_datasource_schema_tool():
    schema = await tableau_get_datasource_schema(
        datasource_id="ds-123"
    )
    
    assert "columns" in schema
    assert "data_types" in schema
    assert len(schema["columns"]) > 0
```

#### Task 10.3: Summary Agent Implementation
**Work Items:**
- [ ] Create `app/services/agents/summary_agent.py`
- [ ] Implement multi-view data export
- [ ] Create cross-view aggregation logic
- [ ] Add summarization pipeline (LLM-based)
- [ ] Implement batch export handling
- [ ] Create report generation (PDF/HTML)

**Success Criteria:**
- Agent exports data from multiple views
- Aggregates data across views correctly
- Generates coherent summaries
- Handles large datasets efficiently
- Produces downloadable reports

**Unit Tests:**
```python
# tests/test_summary_agent.py
def test_summary_agent_multi_view_export():
    agent = SummaryAgent()
    
    result = agent.export_views(
        view_ids=["view-1", "view-2", "view-3"]
    )
    
    assert len(result["datasets"]) == 3
    assert all("data" in ds for ds in result["datasets"])
    assert result["total_rows"] > 0

def test_summary_agent_cross_view_aggregation():
    agent = SummaryAgent()
    
    summary = agent.aggregate_across_views(
        view_ids=["view-1", "view-2"],
        aggregation_type="sum",
        column="sales"
    )
    
    assert "total" in summary
    assert "by_view" in summary
    assert summary["total"] > 0

def test_summary_agent_report_generation():
    agent = SummaryAgent()
    
    report = agent.generate_report(
        view_ids=["view-1", "view-2"],
        format="html",
        include_visualizations=True
    )
    
    assert "<html>" in report["content"]
    assert report["format"] == "html"
    assert len(report["visualizations"]) > 0
```

#### Task 10.4: Export MCP Tools
**Work Items:**
- [ ] Create `mcp_server/tools/export_tools.py`
- [ ] Implement `tableau_export_view_data` tool
- [ ] Implement `tableau_export_crosstab` tool
- [ ] Implement `tableau_export_summary` tool
- [ ] Implement `tableau_batch_export` tool
- [ ] Add format options (CSV, JSON, Excel)

**Success Criteria:**
- Export tools accessible via MCP
- Support multiple export formats
- Handle pagination for large exports
- Batch exports work efficiently
- Progress tracking for long exports

**Unit Tests:**
```python
# tests/test_export_tools.py
@pytest.mark.asyncio
async def test_export_view_data_tool():
    result = await tableau_export_view_data(
        view_id="view-123",
        format="csv"
    )
    
    assert "data" in result
    assert result["format"] == "csv"
    assert result["row_count"] > 0

@pytest.mark.asyncio
async def test_batch_export_tool():
    result = await tableau_batch_export(
        view_ids=["view-1", "view-2", "view-3"],
        format="json"
    )
    
    assert len(result["exports"]) == 3
    assert all("data" in exp for exp in result["exports"])
    assert result["total_rows"] > 0

@pytest.mark.asyncio
async def test_export_crosstab_tool():
    result = await tableau_export_crosstab(
        view_id="view-123",
        row_fields=["Region"],
        col_fields=["Year"],
        measure="Sales"
    )
    
    assert "crosstab" in result
    assert "rows" in result["crosstab"]
    assert "columns" in result["crosstab"]
```

#### Task 10.5: Master Agent Router
**Work Items:**
- [ ] Create `app/services/agents/router.py`
- [ ] Implement intent classification
- [ ] Create agent selection logic
- [ ] Add context passing between agents
- [ ] Implement result formatting
- [ ] Add agent orchestration for multi-step tasks

**Success Criteria:**
- Router correctly identifies intent
- Routes to appropriate agent
- Handles agent failures gracefully
- Supports multi-agent workflows
- Maintains conversation context

**Unit Tests:**
```python
# tests/test_agent_router.py
def test_router_intent_classification():
    router = AgentRouter()
    
    assert router.classify("Show me sales data") == "analyst_agent"
    assert router.classify("Construct a VizQL query") == "vds_agent"
    assert router.classify("Summarize these views") == "summary_agent"

def test_router_agent_selection():
    router = AgentRouter()
    
    agent = router.select_agent("Create a query to find top products")
    assert agent.name == "vds_agent"
    
    agent = router.select_agent("Export and summarize sales views")
    assert agent.name == "summary_agent"

@pytest.mark.asyncio
async def test_router_multi_agent_workflow():
    router = AgentRouter()
    
    # Multi-step task: construct query → execute → summarize
    result = await router.execute_workflow(
        "Query sales by region and summarize the results",
        steps=[
            ("vds_agent", "construct_query"),
            ("analyst_agent", "execute_query"),
            ("summary_agent", "summarize_results")
        ]
    )
    
    assert "query" in result
    assert "data" in result
    assert "summary" in result
```

---

### Phase 11: Multi-Agent Frontend Dashboard ⭐

#### Task 11.1: Agent Dashboard Layout
**Work Items:**
- [ ] Create `frontend/app/agents/page.tsx`
- [ ] Create `frontend/app/agents/layout.tsx`
- [ ] Implement multi-panel layout
- [ ] Add agent selector component
- [ ] Create context/state management
- [ ] Add real-time updates via WebSocket

**Success Criteria:**
- Dashboard renders 3-panel layout
- Agent selection updates active panel
- State persists across agent switches
- WebSocket connections stable
- Responsive on all screen sizes

**Unit Tests:**
```typescript
// __tests__/agents/AgentDashboard.test.tsx
describe('AgentDashboard', () => {
  test('renders all three agent panels', () => {
    render(<AgentDashboard />);
    
    expect(screen.getByText(/analyst agent/i)).toBeInTheDocument();
    expect(screen.getByText(/vizql agent/i)).toBeInTheDocument();
    expect(screen.getByText(/summary agent/i)).toBeInTheDocument();
  });

  test('switches between agents', () => {
    render(<AgentDashboard />);
    
    fireEvent.click(screen.getByText(/vizql agent/i));
    expect(screen.getByTestId('vizql-panel')).toBeVisible();
    
    fireEvent.click(screen.getByText(/summary agent/i));
    expect(screen.getByTestId('summary-panel')).toBeVisible();
  });

  test('maintains context across switches', () => {
    render(<AgentDashboard />);
    
    // Set datasource in analyst
    fireEvent.click(screen.getByText(/analyst agent/i));
    fireEvent.click(screen.getByText(/select datasource/i));
    fireEvent.click(screen.getByText(/sales data/i));
    
    // Switch to VizQL
    fireEvent.click(screen.getByText(/vizql agent/i));
    
    // Datasource context should persist
    expect(screen.getByText(/sales data/i)).toBeInTheDocument();
  });
});
```

#### Task 11.2: VizQL Agent UI Components
**Work Items:**
- [ ] Create `frontend/components/agents/VizQLPanel.tsx`
- [ ] Create `frontend/components/agents/SchemaViewer.tsx`
- [ ] Create `frontend/components/agents/QueryBuilder.tsx`
- [ ] Create `frontend/components/agents/QueryValidator.tsx`
- [ ] Add syntax highlighting for VizQL
- [ ] Add query execution controls

**Success Criteria:**
- VizQL panel displays schema
- Query builder assists construction
- Syntax highlighting works
- Validation feedback immediate
- Execution results formatted

**Unit Tests:**
```typescript
// __tests__/agents/VizQLPanel.test.tsx
describe('VizQLPanel', () => {
  test('displays datasource schema', async () => {
    render(<VizQLPanel datasourceId="ds-123" />);
    
    await waitFor(() => {
      expect(screen.getByText(/columns/i)).toBeInTheDocument();
      expect(screen.getByText(/measures/i)).toBeInTheDocument();
    });
  });

  test('validates query syntax', async () => {
    render(<VizQLPanel />);
    
    const input = screen.getByPlaceholderText(/enter vizql query/i);
    fireEvent.change(input, { target: { value: 'INVALID SYNTAX' } });
    
    await waitFor(() => {
      expect(screen.getByText(/syntax error/i)).toBeInTheDocument();
    });
  });

  test('executes valid query', async () => {
    render(<VizQLPanel />);
    
    const input = screen.getByPlaceholderText(/enter vizql query/i);
    fireEvent.change(input, { 
      target: { value: 'SELECT SUM([Sales]) FROM datasource' }
    });
    
    fireEvent.click(screen.getByText(/execute/i));
    
    await waitFor(() => {
      expect(screen.getByText(/results/i)).toBeInTheDocument();
    });
  });
});
```

#### Task 11.3: Summary Agent UI Components
**Work Items:**
- [ ] Create `frontend/components/agents/SummaryPanel.tsx`
- [ ] Create `frontend/components/agents/ViewSelector.tsx`
- [ ] Create `frontend/components/agents/ExportOptions.tsx`
- [ ] Create `frontend/components/agents/SummaryViewer.tsx`
- [ ] Add progress indicators for exports
- [ ] Add download controls

**Success Criteria:**
- Summary panel allows multi-view selection
- Export options configurable
- Progress tracked for long operations
- Summary rendered in readable format
- Download works for all formats

**Unit Tests:**
```typescript
// __tests__/agents/SummaryPanel.test.tsx
describe('SummaryPanel', () => {
  test('allows multiple view selection', () => {
    render(<SummaryPanel />);
    
    fireEvent.click(screen.getByText(/select views/i));
    
    const view1 = screen.getByLabelText(/sales dashboard/i);
    const view2 = screen.getByLabelText(/regional report/i);
    
    fireEvent.click(view1);
    fireEvent.click(view2);
    
    expect(screen.getByText(/2 views selected/i)).toBeInTheDocument();
  });

  test('exports data with progress tracking', async () => {
    render(<SummaryPanel />);
    
    // Select views and export
    fireEvent.click(screen.getByText(/export/i));
    
    // Check progress indicator appears
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText(/export complete/i)).toBeInTheDocument();
    });
  });

  test('generates summary report', async () => {
    render(<SummaryPanel viewIds={['view-1', 'view-2']} />);
    
    fireEvent.click(screen.getByText(/generate summary/i));
    
    await waitFor(() => {
      expect(screen.getByText(/summary report/i)).toBeInTheDocument();
      expect(screen.getByText(/key findings/i)).toBeInTheDocument();
    });
  });
});
```

#### Task 11.4: Agent API Endpoints
**Work Items:**
- [ ] Create `backend/app/api/agents.py`
- [ ] Implement `POST /api/agents/vds/construct-query`
- [ ] Implement `POST /api/agents/vds/execute-query`
- [ ] Implement `POST /api/agents/summary/export-views`
- [ ] Implement `POST /api/agents/summary/generate-summary`
- [ ] Implement `GET /api/agents/router/classify`
- [ ] Add WebSocket endpoints for streaming results

**Success Criteria:**
- All agent endpoints functional
- Request/response validation via Pydantic
- Error handling comprehensive
- WebSocket streaming works
- API documented in Swagger

**Unit Tests:**
```python
# tests/test_agents_api.py
def test_vds_construct_query_endpoint(client):
    response = client.post("/api/agents/vds/construct-query", json={
        "user_query": "Show total sales by region",
        "datasource_id": "ds-123"
    })
    
    assert response.status_code == 200
    assert "vizql" in response.json()
    assert response.json()["valid"] is True

def test_summary_export_views_endpoint(client):
    response = client.post("/api/agents/summary/export-views", json={
        "view_ids": ["view-1", "view-2"],
        "format": "csv"
    })
    
    assert response.status_code == 200
    assert "exports" in response.json()
    assert len(response.json()["exports"]) == 2

def test_summary_generate_summary_endpoint(client):
    response = client.post("/api/agents/summary/generate-summary", json={
        "view_ids": ["view-1", "view-2"],
        "format": "html"
    })
    
    assert response.status_code == 200
    assert "summary" in response.json()
    assert "html" in response.json()["format"]

@pytest.mark.asyncio
async def test_agent_websocket_streaming(client):
    async with client.websocket_connect("/ws/agents/vds") as ws:
        await ws.send_json({
            "action": "construct_query",
            "user_query": "Sales by region"
        })
        
        response = await ws.receive_json()
        assert "vizql" in response
```

#### Task 11.5: End-to-End Integration
**Work Items:**
- [ ] Test VizQL agent full workflow (frontend → backend → MCP → Tableau)
- [ ] Test summary agent full workflow
- [ ] Test agent switching with context preservation
- [ ] Test multi-agent workflows
- [ ] Performance testing with large datasets
- [ ] Load testing with concurrent users

**Success Criteria:**
- All agent workflows complete successfully
- No data loss on agent switches
- Multi-agent workflows orchestrate correctly
- Performance acceptable (<2s response time)
- System handles 50+ concurrent users

**Integration Tests:**
```python
# tests/integration/test_agent_workflows.py
@pytest.mark.asyncio
async def test_vds_agent_end_to_end():
    # 1. User asks question
    response = await client.post("/api/agents/router/route", json={
        "query": "Show me total sales by region for 2024"
    })
    assert response.json()["agent"] == "vds_agent"
    
    # 2. VizQL agent constructs query
    construct_response = await client.post("/api/agents/vds/construct-query", json={
        "user_query": response.json()["query"],
        "datasource_id": "ds-123"
    })
    vizql = construct_response.json()["vizql"]
    
    # 3. Execute query
    execute_response = await client.post("/api/agents/vds/execute-query", json={
        "datasource_id": "ds-123",
        "vizql_query": vizql
    })
    
    assert execute_response.status_code == 200
    assert len(execute_response.json()["data"]) > 0

@pytest.mark.asyncio
async def test_multi_agent_workflow():
    # Workflow: VizQL agent constructs → Analyst executes → Summary agent summarizes
    
    # Step 1: Construct query (VizQL agent)
    construct = await client.post("/api/agents/vds/construct-query", json={
        "user_query": "Regional sales analysis",
        "datasource_id": "ds-123"
    })
    
    # Step 2: Execute query (Analyst agent)
    execute = await client.post("/api/agents/analyst/execute", json={
        "vizql_query": construct.json()["vizql"],
        "datasource_id": "ds-123"
    })
    
    # Step 3: Summarize results (Summary agent)
    summary = await client.post("/api/agents/summary/summarize-data", json={
        "data": execute.json()["data"],
        "context": "Regional sales analysis"
    })
    
    assert "summary" in summary.json()
    assert "key_findings" in summary.json()
```

---
- [ ] Test Tableau integration end-to-end
- [ ] Test AI provider fallback
- [ ] Test error recovery

**Success Criteria:**
- All integration tests pass
- Tests cover happy path and error cases
- Tests run in CI/CD pipeline

**Unit Tests:**
```python
# tests/integration/test_chat_flow.py
def test_complete_chat_flow(client, db_session):
    # Create conversation
    conv_response = client.post("/api/chat/conversations")
    conv_id = conv_response.json()["id"]
    
    # User asks to list datasources
    msg1 = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "content": "List all datasources",
        "model": "gpt-4"
    })
    assert "datasource" in msg1.json()["content"].lower()
    
    # User asks to query a datasource
    msg2 = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "content": "Query the sales datasource for 2024 data",
        "model": "gpt-4"
    })
    assert msg2.status_code == 200
    
    # Verify conversation history
    history = client.get(f"/api/chat/conversations/{conv_id}/messages")
    assert len(history.json()) >= 4  # 2 user + 2 assistant messages
```

#### Task 9.2: MCP Server Integration Tests
**Work Items:**
- [ ] Test end-to-end MCP tool invocation from IDE
- [ ] Test MCP tool invocation from web (SSE)
- [ ] Test conversation flow via MCP
- [ ] Test authentication flow via MCP
- [ ] Test resource access patterns
- [ ] Load test MCP server with concurrent connections

**Success Criteria:**
- IDE can complete full workflow via MCP
- Web can complete full workflow via MCP
- Concurrent connections handled correctly
- No memory leaks under load
- Error handling works across MCP boundary

**Unit Tests:**
```python
# tests/integration/test_mcp_flow.py
@pytest.mark.asyncio
async def test_complete_mcp_workflow_from_ide():
    """Test complete workflow: auth -> list datasources -> query -> get results"""
    # 1. Authenticate
    auth_result = await call_mcp_tool("auth_tableau_signin", {
        "server_url": "https://tableau.test.com",
        "client_id": "test-id",
        "client_secret": "test-secret"
    })
    assert auth_result["authenticated"]
    
    # 2. List datasources
    ds_result = await call_mcp_tool("tableau_list_datasources", {})
    assert len(ds_result["datasources"]) > 0
    
    # 3. Query first datasource
    ds_id = ds_result["datasources"][0]["id"]
    query_result = await call_mcp_tool("tableau_query_datasource", {
        "datasource_id": ds_id,
        "filters": {"year": "2024"}
    })
    assert "data" in query_result

@pytest.mark.asyncio
async def test_mcp_conversation_via_sse():
    """Test conversation management via SSE transport"""
    async with SSEClient("/mcp/sse") as client:
        # Create conversation
        conv = await client.call_tool("chat_create_conversation", {})
        conv_id = conv["conversation_id"]
        
        # Add messages
        await client.call_tool("chat_add_message", {
            "conversation_id": conv_id,
            "role": "user",
            "content": "Show me sales data"
        })
        
        # Retrieve conversation as resource
        resource = await client.read_resource(f"conversation://{conv_id}")
        assert len(resource["messages"]) == 1

@pytest.mark.asyncio
async def test_mcp_load_handling():
    """Test MCP server under load"""
    async with asyncio.TaskGroup() as tg:
        tasks = []
        for i in range(50):
            task = tg.create_task(
                call_mcp_tool("tableau_list_datasources", {})
            )
            tasks.append(task)
        
        results = [task.result() for task in tasks]
        assert all("datasources" in r for r in results)
```

#### Task 9.3: Docker & Deployment
**Work Items:**
- [ ] Create `backend/Dockerfile`
- [ ] Create `frontend/Dockerfile`
- [ ] Create `mcp_server/Dockerfile`
- [ ] Update `docker-compose.yml` with all services (FastAPI, Frontend, PostgreSQL, MCP Server)
- [ ] Add health checks to containers
- [ ] Create CI/CD pipeline (GitHub Actions)
- [ ] Write deployment documentation
- [ ] Document MCP server deployment (stdio vs SSE)

**Success Criteria:**
- `docker-compose up` starts all services
- Health checks pass
- Environment variables properly injected
- CI/CD runs tests and builds images

**Unit Tests:**
```bash
# Test Docker builds
docker build -t tableau-demo-backend backend/
docker build -t tableau-demo-frontend frontend/
docker build -t tableau-demo-gateway backend/ -f backend/Dockerfile.gateway
docker build -t tableau-demo-mcp backend/ -f backend/Dockerfile.mcp

# Test docker-compose
docker-compose up -d
docker-compose ps | grep "Up"

# Test health endpoints
curl http://localhost:8000/health  # Backend
curl http://localhost:3000  # Frontend
curl http://localhost:8001/gateway/health  # Gateway
curl http://localhost:8002/health  # MCP server

# Test database connectivity
docker-compose exec backend python -c "from app.core.database import engine; engine.connect()"

# Test Redis connectivity
docker-compose exec backend python -c "from app.core.cache import redis_client; print(redis_client.ping())"

# Test gateway routing
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'

# Test MCP server
docker-compose exec mcp-server python -c "from mcp_server.server import create_server; server = create_server(); print('MCP OK')"

# Test MCP SSE endpoint
curl http://localhost:8002/mcp/sse
```

---

## Progress Tracking Checklist

### Quick Start Verification
- [ ] Backend server runs on port 8000
- [ ] Frontend server runs on port 3000
- [ ] Gateway server runs on port 8001
- [ ] MCP server runs on port 8002
- [ ] PostgreSQL accessible
- [ ] Redis accessible
- [ ] Environment variables loaded
- [ ] All tests pass: `pytest && npm test`
- [ ] Gateway health check passes: `curl http://localhost:8001/gateway/health`

### Core Functionality Checklist
- [ ] User can create new conversation
- [ ] User can send messages
- [ ] AI responds to messages
- [ ] Chat history persists
- [ ] Tableau datasources can be listed
- [ ] Tableau views can be embedded
- [ ] Datasources can be queried
- [ ] Function calling works for all tools
- [ ] Multiple AI models selectable
- [ ] Error handling works throughout
- [ ] **Unified LLM Gateway routing works for all providers**
- [ ] **OpenAI models work via gateway (GPT-4, GPT-3.5)**
- [ ] **Anthropic models work via gateway (Claude)**
- [ ] **Salesforce models work with JWT OAuth and Trust Layer**
- [ ] **Vertex AI models work with service account (Gemini)**
- [ ] **OAuth tokens cached in Redis with proper TTL**
- [ ] **Gateway normalizes all responses to OpenAI format**
- [ ] **MCP server accessible from IDE (Cursor/VS Code)**
- [ ] **MCP tools callable via stdio transport**
- [ ] **MCP tools callable via SSE transport (web)**
- [ ] **MCP resources readable (conversations, datasources, views)**
- [ ] **MCP authentication works (Tableau Connected Apps)**

### Multi-Agent Functionality Checklist
- [ ] **Master agent router classifies intent correctly**
- [ ] **VizQL agent constructs valid queries from natural language**
- [ ] **VizQL agent validates query syntax**
- [ ] **VizQL agent executes queries successfully**
- [ ] **Summary agent exports data from multiple views**
- [ ] **Summary agent generates coherent summaries**
- [ ] **Summary agent produces downloadable reports**
- [ ] **Agent dashboard renders all three agents**
- [ ] **Agent switching preserves context**
- [ ] **Multi-agent workflows orchestrate correctly**
- [ ] **VizQL tools accessible via MCP**
- [ ] **Export tools accessible via MCP**
- [ ] **WebSocket streaming works for all agents**

### Production Readiness Checklist
- [ ] All unit tests pass (>90% coverage)
- [ ] All integration tests pass
- [ ] Load testing complete
- [ ] Security audit complete
- [ ] Documentation complete
- [ ] Docker images build successfully
- [ ] CI/CD pipeline runs successfully
- [ ] Environment-specific configs ready
- [ ] **MCP server tested in production-like environment**
- [ ] **MCP security reviewed (credential storage, token handling)**
- [ ] **MCP documentation complete (setup, usage, troubleshooting)**

---

## Multi-Agent Architecture

### Current Agents

1. **analyst_agent** (existing)
   - General Tableau queries
   - List datasources/views
   - Basic data queries
   - View embedding

2. **vds_agent** (NEW - Phase 10)
   - VizQL Data Service query construction
   - Natural language to VizQL translation
   - Datasource schema understanding
   - Query optimization

3. **summary_agent** (NEW - Phase 10)
   - Multi-view data export
   - Cross-view summarization
   - Aggregate analysis
   - Report generation

### Agent Coordination Pattern

```python
# Master Agent Router
class AgentRouter:
    def route(self, user_query: str, context: dict) -> Agent:
        intent = self.classifier.classify(user_query)
        
        if "vizql" in intent or "query syntax" in intent:
            return self.vds_agent
        elif "summarize" in intent or "export" in intent:
            return self.summary_agent
        else:
            return self.analyst_agent
    
    async def execute(self, query: str, agent: Agent):
        # Execute with agent-specific tools and prompts
        return await agent.run(query, tools=agent.allowed_tools)
```

### Frontend Dashboard

Multi-panel interface showcasing each agent:

```
┌────────────────────────────────────────────────────────────┐
│  Agent Selector: [Analyst] [VizQL] [Summary]              │
├──────────────────┬─────────────────────────────────────────┤
│                  │                                         │
│  Query Panel     │  Results Panel                          │
│  ┌────────────┐  │  ┌───────────────────────────────────┐ │
│  │ User input │  │  │ • VizQL Query                     │ │
│  │            │  │  │ • Execution results               │ │
│  │ [Send]     │  │  │ • Summary statistics              │ │
│  └────────────┘  │  │ • Visualizations                  │ │
│                  │  └───────────────────────────────────┘ │
│  Context Panel   │  Export Panel                          │
│  • Datasources   │  • Download CSV                        │
│  • Selected cols │  • Download JSON                       │
│  • Filters       │  • Copy to clipboard                   │
└──────────────────┴─────────────────────────────────────────┘
```

## Future Agent Suite Integration

This demo tool implements **three specialized agents** as part of the broader **Unified Tableau AI Agent Suite**. The MCP architecture enables future expansion to include:

### Planned Future Agents

1. **Administrator Agent ("The Gatekeeper")**
   - Zombie content cleanup
   - Security auditing
   - Permission management
   
2. **Creator Agent ("The Builder")**
   - XML workbook manipulation
   - LOD expression generation
   - Style enforcement

3. **Steward Agent ("The Auditor")**
   - Impact analysis via Metadata API
   - Data quality warnings
   - Dependency tracking

### Agent Foundation

By exposing Tableau operations, conversation management, and authentication via MCP, this demo establishes the foundational protocol that all future agents will use. The "write-once, deploy-anywhere" strategy ensures agents work seamlessly across IDEs (Cursor, VS Code) and web interfaces without code duplication.

**Reference:** See `PRD_ AI Agent Suite for Tableau.md` for full agent suite roadmap.

---

## Unified LLM Gateway Benefits

The Unified LLM Gateway architecture provides significant advantages over direct provider integration:

### 1. **Agent Simplicity**
- Agents use a single OpenAI-compatible interface for all models
- No need to learn provider-specific APIs (Vertex AI format, Salesforce format, etc.)
- Consistent function calling across all providers

### 2. **Security & Compliance**
- **Credential Isolation**: API keys and service account JSONs never exposed to agents
- **Salesforce Trust Layer**: Automatic PII masking via Einstein Trust Layer integration
- **Centralized Auth**: Single point for managing OAuth flows and token rotation
- **Audit Trail**: All LLM requests logged and auditable at gateway level

### 3. **Performance Optimization**
- **Token Caching**: OAuth tokens cached in Redis (reduces auth overhead by ~95%)
- **Connection Pooling**: Persistent connections to backend providers
- **Smart Retry**: Provider-specific retry logic with exponential backoff
- **Load Balancing**: Future support for multi-region model routing

### 4. **Cost Management**
- **Unified Metering**: Track token usage across all providers in one place
- **Model Fallback**: Automatic fallback to cheaper models on rate limits
- **Budget Controls**: Set spending limits per provider/model
- **Usage Analytics**: Identify high-cost queries and optimize

### 5. **Operational Excellence**
- **Health Monitoring**: Single dashboard for all provider health
- **Circuit Breakers**: Automatically disable failing providers
- **Version Management**: Test new provider API versions without code changes
- **Provider Agnostic**: Swap providers (e.g., OpenAI → Azure OpenAI) via config only

### 6. **Future Extensibility**
The gateway architecture supports future capabilities without agent changes:
- **Prompt Caching**: Cache common prompts at gateway level
- **Content Filtering**: Apply consistent content policies across all providers
- **Multi-Model Routing**: Route to best model based on query type
- **A/B Testing**: Compare provider responses for quality analysis

### Gateway vs Direct Integration Comparison

| Aspect | Direct Integration | Unified Gateway |
|--------|-------------------|-----------------|
| **Code Complexity** | 4 separate provider implementations | Single client implementation |
| **Auth Management** | 4 different auth flows | Centralized, cached tokens |
| **Format Handling** | Handle 4 different formats | OpenAI format only |
| **Security** | Credentials in app code | Credentials in gateway only |
| **Monitoring** | 4 separate dashboards | Single monitoring point |
| **Provider Switch** | Code changes required | Config change only |
| **Testing** | Mock 4 providers | Mock 1 gateway |
| **Performance** | Repeated auth flows | Cached tokens (-95% auth time) |

**Recommended Reading:**
- `Unified LLM Gateway Technical Specification.md` - Detailed gateway implementation
- `PRD_ AI Agent Suite for Tableau.md` - How gateway enables multi-agent architecture
- `AGENT_IMPLEMENTATION.md` - Next steps for implementing Summary, VizQL, and General agents
