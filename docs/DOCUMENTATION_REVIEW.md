# Documentation Review

Technical writer review of the Tableau AI Demo documentation. This document captures fixes applied, remaining unclear items, and recommendations.

## Fixes Applied

### README.md
- **Health endpoint**: Corrected `/health` → `/api/v1/health`
- **API docs URL**: Corrected `/docs` → `/api/v1/docs`
- **Python version**: Corrected `3.12+` → `3.11+` (matches `pyproject.toml` requires-python)
- **Quick Start paths**: Added `cd main` after clone; clarified infra compose for Postgres/Redis
- **Infrastructure**: Replaced `docker-compose up -d postgres redis` with `docker compose -f docker-compose.infra.yml -p tableau-demo-infra up -d`

### DEPLOYMENT.md
- **Clone path**: Added `cd main` for correct working directory
- **Infrastructure**: Added step to start Postgres/Redis via `docker-compose.infra.yml` before app services
- **Build commands**: Removed non-existent `gateway` and `mcp-server` services (Gateway and MCP are integrated into backend)
- **mcp-server service**: Clarified that MCP SSE is integrated into backend at `/mcp/sse`
- **docker-compose → docker compose**: Standardized on v2 plugin syntax (filenames remain `docker-compose.*.yml`)

### Architecture (ARCHITECTURE.md)
- **Python version**: Updated `Python 3.11` → `Python 3.11+` for Backend, Gateway, MCP
- **Health endpoints**: Corrected to `/api/v1/health` and `/api/v1/gateway/health`

### MCP Server (backend/mcp_server/)
- **Python version**: `3.10+` → `3.11+` in README, TROUBLESHOOTING
- **Duplicate section**: Removed duplicate "Tools not appearing in IDE" heading in README
- **SSE connection**: Clarified EventSource must use full backend URL (`NEXT_PUBLIC_API_URL/mcp/sse`)
- **Health check**: Corrected `/health` → `/api/v1/health` in TESTING.md

### DOCKER_DEV.md
- **Environment path**: Clarified "From repo root, copy `main/.env.example` to `shared/.env`"
- **API docs**: Corrected `/docs` → `/api/v1/docs`

### REGRESSION_TEST_PLAN.md
- **Health endpoint**: Corrected `GET /health` → `GET /api/v1/health`

---

## Unclear or Needs Follow-up

### 1. Project Root vs. `main/` Directory
**Issue**: Repo structure uses `main/` as the app directory. Quick Start now says `cd tableau-ai-demo/main`, but some docs assume different roots (e.g., `shared/` is sibling to `main/`).

**Recommendation**: Add a "Repository Structure" section to README:
```
tableau-ai-demo/
├── main/           # Application (backend, frontend, docker-compose)
├── shared/         # Shared .env and certs (worktrees)
└── ...
```

### 2. DEPLOYMENT.md – Postgres/Redis Exec Commands
**Issue**: Troubleshooting uses `docker compose exec postgres` and `docker compose exec redis`. Postgres and Redis are in `docker-compose.infra.yml`, not the main compose. These commands will fail unless run with:
```bash
docker compose -f docker-compose.infra.yml -p tableau-demo-infra exec postgres ...
```

**Recommendation**: Add a note or use the `-f` and `-p` flags in troubleshooting examples.

### 3. MCP_SERVER_DEPLOYMENT.md – Port 8002
**Issue**: Doc describes standalone MCP on port 8002, but the primary deployment uses MCP integrated into backend on port 8000. The standalone Docker section may confuse readers.

**Recommendation**: Add a clear "Primary: Integrated Backend" vs "Alternative: Standalone" section at the top.

### 4. Gateway Provider Support
**Issue**: ARCHITECTURE.md lists Anthropic, Salesforce, Vertex AI as supported. README lists only OpenAI and Apple Endor. Actual support may differ.

**Recommendation**: Audit gateway providers and align docs with implemented providers.

### 5. Frontend README
**Issue**: `frontend/README.md` is the default Next.js template (Geist font, Vercel deploy). It does not describe Tableau integration, HTTPS, or project-specific setup.

**Recommendation**: Replace or extend with project-specific frontend docs (HTTPS, Tableau embed, API client, etc.).

### 6. HTTPS_SETUP.md – mkcert Option
**Fixed**: Removed redundant `mv` commands. `mkcert localhost` creates `localhost.pem` and `localhost-key.pem` directly.

### 7. MULTI_AGENT_ARCHITECTURE.md – Agent Naming
**Issue**: Uses `analyst_agent`, `vds_agent`, `summary_agent`. README uses "General Agent", "VizQL Agent", "Summary Agent". Mapping is implicit.

**Recommendation**: Add a small table mapping doc names to UI/API names.

### 8. Placeholder Sections
**Issue**: README has `[Your License Here]` and `[Contributing Guidelines]`.

**Recommendation**: Add real content or remove if not applicable.

---

## Documentation Quality Summary

| Doc | Accuracy | Completeness | Clarity |
|-----|----------|--------------|---------|
| README | ✓ Fixed | Good | Good |
| ARCHITECTURE | ✓ Fixed | Good | Good |
| DEPLOYMENT | ✓ Fixed | Good | Minor gaps (infra exec) |
| DOCKER_DEV | ✓ Fixed | Good | Good |
| MCP README | ✓ Fixed | Good | Good |
| MCP_SERVER_DEPLOYMENT | Partial | Mixed contexts | Needs restructure |
| Frontend README | N/A | Boilerplate | Replace |
| HTTPS_SETUP | Check mkcert | Good | Good |

---

## Recommended Next Steps

1. Fix mkcert `mv` commands in HTTPS_SETUP.md
2. Add repository structure diagram to README
3. Update DEPLOYMENT troubleshooting with correct `-f`/`-p` for infra services
4. Restructure MCP_SERVER_DEPLOYMENT to prioritize integrated deployment
5. Replace frontend README with project-specific content
6. Align gateway provider list across all docs
