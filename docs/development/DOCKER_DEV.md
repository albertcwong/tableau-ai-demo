# Docker Development Guide

Develop entirely in Docker with hot reload. Use `./scripts/dev-docker.sh` for dynamic ports (enables parallel worktrees and agent-created worktrees in arbitrary paths).

## Quick Start

```bash
# Ensure Postgres and Redis are running locally (e.g. docker compose up -d postgres redis, or native install)

# Start stack (ports derived from PWD; URLs printed after start)
./scripts/dev-docker.sh up --build

# Detached
./scripts/dev-docker.sh up -d --build

# Get URLs without starting
./scripts/dev-docker.sh url

# Stop
./scripts/dev-docker.sh down
```

**URLs** (dynamic; run `./scripts/dev-docker.sh url` to see yours):
- Frontend: `https://localhost:<port>` (HTTPS; required for Tableau embed)
- Backend: `http://localhost:<port>`
- API Docs: `http://localhost:<port>/docs`

## Prerequisites

1. **Postgres and Redis**: Running on localhost (default ports 5432, 6379). Containers connect via `host.docker.internal`. Override with `DATABASE_URL` and `REDIS_URL` in `.env` if using different ports. If you need Docker postgres/redis: `docker compose -f docker-compose.infra.yml -p tableau-demo-infra up -d` (then use `postgresql://postgres:postgres@host.docker.internal:5432/tableau_demo`).

2. **Environment**: Copy `.env.example` to `shared/.env` and configure (worktrees symlink from `shared/`).

3. **Worktree setup**:
   - **Cursor worktrees**: `.env` and certs linked via `.cursor/worktrees.json`.
   - **Manual worktrees** (`git worktree add`): Run `./scripts/setup-worktree-env.sh` once.

4. **Certificates**: Generate in `shared/` (from project root; worktrees use `../shared`):
   ```bash
   cd shared && ./generate-cert.sh
   ```
   Trust in browser: Keychain Access (macOS) or `chrome://settings/certificates` → Import `localhost.pem`.

5. **Database**: Run migrations on first run:
   ```bash
   ./scripts/dev-docker.sh run backend alembic upgrade head
   ```

## How It Works

| Component | Development |
|-----------|-------------|
| Backend | Volume mount `./backend/app`, `./backend/mcp_server`; uvicorn `--reload` |
| Frontend | Volume mount `./frontend`; `npm run dev`; named volume for `node_modules` |
| Postgres/Redis | Use local (host.docker.internal:5432, :6379) |

**Dynamic ports**: Ports are derived from `PWD` (same path = same ports). Enables parallel worktrees and agent-created worktrees without port conflicts.

**Certificates**: Mounted from `shared/` via `CERT_PATH` (set by `setup-worktree-env.sh` for manual worktrees).

## Docker Dev vs Local Dev

| Use Docker Dev when | Use Local Dev when |
|---------------------|-------------------|
| Verifying Docker deployment | Faster iteration on one service |
| Onboarding new developers | Debugging with IDE breakpoints |
| CI/CD pipeline testing | Prefer native tooling |
| Agent-created worktrees | Single worktree workflow |

**Local dev**:
```bash
# Start postgres/redis first (e.g. docker compose up -d postgres redis from project root)
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Troubleshooting

### Backend changes not reloading
- Ensure `./backend/app` and `./backend/mcp_server` exist
- Check logs: `./scripts/dev-docker.sh logs -f backend`

### Frontend "Cannot find module"
- Rebuild: `./scripts/dev-docker.sh build --no-cache frontend`
- Reset node_modules: `docker volume ls` → `docker volume rm <wt-*_frontend_node_modules>`

### Containers using old directory (after worktree change)
- Run `./scripts/setup-worktree-env.sh` to regenerate `PROJECT_ROOT` and `CERT_PATH`
- `./scripts/dev-docker.sh down` then `./scripts/dev-docker.sh up --build`

### Certificates / HTTPS
- Generate: `cd shared && ./generate-cert.sh` (Tableau embed requires HTTPS)
- If missing, frontend falls back to HTTP on port 3001

### Port conflicts
- Ports are dynamic; conflicts are rare. If needed, `./scripts/dev-docker.sh down` and restart.
