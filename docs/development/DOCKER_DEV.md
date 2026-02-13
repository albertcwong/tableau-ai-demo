# Docker Development Guide

Develop entirely in Docker with hot reload. This catches Docker-specific issues during development instead of at deployment.

## Quick Start

```bash
# Start infrastructure + backend + frontend with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or use the script
./scripts/dev-docker.sh --build

# Or run in background
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**URLs:**
- Frontend: https://localhost:3000 (HTTPS; required for Tableau embed; HMR works with Next.js built-in server)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Prerequisites

1. **Environment**: Copy `.env.example` to `.env` and configure
2. **Certificates** (optional): For HTTPS, run `cd frontend && ./generate-cert.sh`
3. **Database**: Run migrations on first run:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml run backend alembic upgrade head
   ```

## How It Works

| Component | Production | Development |
|-----------|------------|-------------|
| Backend | Built image, no reload | Volume mount `./backend/app`, `./backend/mcp_server`, uvicorn `--reload` |
| Frontend | Built Next.js standalone | Volume mount `./frontend`, `npm run dev`, named volume for `node_modules` |
| Postgres/Redis | Same | Same |

**Volume strategy:**
- Backend: Source code mounted; changes trigger uvicorn reload
- Frontend: Source mounted; `node_modules` uses named volume (avoids host/container architecture mismatch)
- Certificates: Mounted from `frontend/localhost-key.pem`, `frontend/localhost.pem`

## Docker Dev vs Local Dev

| Use Docker Dev when | Use Local Dev when |
|---------------------|-------------------|
| Verifying Docker deployment | Faster iteration on one service |
| Onboarding new developers | Debugging with IDE breakpoints |
| CI/CD pipeline testing | Prefer native tooling |
| Catching env/path differences | Working offline with cached deps |

**Local dev** (existing workflow):
```bash
docker-compose up -d postgres redis
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Troubleshooting

### Backend changes not reloading
- Ensure `./backend/app` and `./backend/mcp_server` exist
- Check logs: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend`

### Frontend "Cannot find module"
- Rebuild: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache frontend`
- Reset node_modules volume: `docker volume ls` to find it, then `docker volume rm <volume_name>` and `up --build`

### Certificates / HTTPS
- Generate certs: `cd frontend && ./generate-cert.sh` (required for Docker dev; Tableau embed needs HTTPS)
- Docker dev uses `next dev --experimental-https` with your certs—HMR WebSocket works

### Port conflicts
- Ensure ports 3000, 3001, 5432, 6379, 8000 are free
- Stop other Docker stacks: `docker-compose down`
