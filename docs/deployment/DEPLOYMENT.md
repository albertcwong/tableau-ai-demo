# Deployment Guide

This guide covers deploying the Tableau AI Demo application using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available
- Ports 3000, 5432, 6379, 8000, 8001, 8002 available

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tableau-ai-demo
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Set up credentials**
   ```bash
   # Place your service account JSON files in credentials/
   # - vertex-sa.json (for Vertex AI)
   # - salesforce-private-key.pem (for Salesforce)
   ```

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Verify services are running**
   ```bash
   docker-compose ps
   ```

6. **Check health endpoints**
   ```bash
   curl http://localhost:8000/health      # Backend
   curl http://localhost:3000             # Frontend
   curl http://localhost:8001/gateway/health  # Gateway
   curl http://localhost:8002/mcp/debug/tools # MCP Server
   ```

## Architecture

The application consists of the following services:

- **postgres**: PostgreSQL 15 database
- **redis**: Redis 7 cache for OAuth tokens
- **gateway**: Unified LLM Gateway (port 8001)
- **backend**: FastAPI backend (port 8000)
- **mcp-server**: MCP Server (port 8002, SSE transport)
- **frontend**: Next.js frontend (port 3000)

## Environment Variables

### Required Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tableau_demo

# Redis
REDIS_URL=redis://redis:6379/0

# Tableau
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_SITE_ID=your-site-id
TABLEAU_CLIENT_ID=your-connected-app-client-id
TABLEAU_CLIENT_SECRET=your-connected-app-secret

# Gateway
GATEWAY_BASE_URL=http://gateway:8001

# AI Provider Credentials (at least one required)
OPENAI_API_KEY=your-openai-key
# OR
ANTHROPIC_API_KEY=your-anthropic-key
# OR
SALESFORCE_CLIENT_ID=your-salesforce-client-id
SALESFORCE_USERNAME=your-service-account@company.com
# OR
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=us-central1
```

### Optional Variables

```bash
# MCP Server
MCP_SERVER_NAME=tableau-analyst-agent
MCP_TRANSPORT=sse  # or stdio
MCP_LOG_LEVEL=info

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Building Images

### Build all images
```bash
docker-compose build
```

### Build specific service
```bash
docker-compose build backend
docker-compose build frontend
docker-compose build gateway
docker-compose build mcp-server
```

### Build without cache
```bash
docker-compose build --no-cache
```

## Running Services

### Start all services
```bash
docker-compose up -d
```

### Start specific service
```bash
docker-compose up -d backend
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop services
```bash
docker-compose down
```

### Stop and remove volumes
```bash
docker-compose down -v
```

## Health Checks

All services include health checks:

- **Backend**: `http://localhost:8000/health`
- **Frontend**: `http://localhost:3000`
- **Gateway**: `http://localhost:8001/gateway/health`
- **MCP Server**: `http://localhost:8002/mcp/debug/tools`

Check health status:
```bash
docker-compose ps
```

## Database Migrations

Run migrations on first startup or after schema changes:

```bash
docker-compose exec backend alembic upgrade head
```

Create new migration:
```bash
docker-compose exec backend alembic revision --autogenerate -m "description"
```

## Troubleshooting

### Services won't start

1. Check logs:
   ```bash
   docker-compose logs
   ```

2. Verify environment variables:
   ```bash
   docker-compose config
   ```

3. Check port availability:
   ```bash
   lsof -i :8000
   lsof -i :3000
   ```

### Database connection errors

1. Verify PostgreSQL is healthy:
   ```bash
   docker-compose exec postgres pg_isready -U postgres
   ```

2. Check database URL in environment:
   ```bash
   docker-compose exec backend env | grep DATABASE_URL
   ```

### Redis connection errors

1. Verify Redis is healthy:
   ```bash
   docker-compose exec redis redis-cli ping
   ```

2. Check Redis URL:
   ```bash
   docker-compose exec backend env | grep REDIS_URL
   ```

### Frontend build errors

1. Clear Next.js cache:
   ```bash
   docker-compose exec frontend rm -rf .next
   docker-compose restart frontend
   ```

2. Rebuild frontend:
   ```bash
   docker-compose build --no-cache frontend
   ```

## Production Deployment

### Security Considerations

1. **Change default passwords**
   - Update PostgreSQL password
   - Use strong Redis password if exposed

2. **Use secrets management**
   - Store credentials in Docker secrets or external secret manager
   - Never commit `.env` files

3. **Enable HTTPS**
   - Use reverse proxy (nginx, Traefik) with SSL certificates
   - Configure CORS properly

4. **Network isolation**
   - Use Docker networks to isolate services
   - Only expose necessary ports

### Scaling

Scale services horizontally:

```bash
# Scale backend
docker-compose up -d --scale backend=3

# Scale frontend
docker-compose up -d --scale frontend=2
```

Use a load balancer (nginx, Traefik) in front of scaled services.

### Monitoring

Add monitoring stack:

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    # ... configuration
  
  grafana:
    image: grafana/grafana
    # ... configuration
```

## MCP Server Deployment

See [MCP_SERVER_DEPLOYMENT.md](./MCP_SERVER_DEPLOYMENT.md) for detailed MCP server deployment instructions.

## CI/CD

GitHub Actions workflows are configured for:

- **CI**: Runs tests on push/PR
- **Docker Build**: Builds and pushes images on main branch

See `.github/workflows/` for details.

## Backup and Restore

### Backup database
```bash
docker-compose exec postgres pg_dump -U postgres tableau_demo > backup.sql
```

### Restore database
```bash
docker-compose exec -T postgres psql -U postgres tableau_demo < backup.sql
```

### Backup volumes
```bash
docker run --rm -v tableau-demo_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data
```

## Updates and Upgrades

1. Pull latest changes:
   ```bash
   git pull
   ```

2. Rebuild images:
   ```bash
   docker-compose build
   ```

3. Restart services:
   ```bash
   docker-compose up -d
   ```

4. Run migrations:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

## Support

For issues and questions:
- Check logs: `docker-compose logs`
- Review [TROUBLESHOOTING.md](./backend/mcp_server/TROUBLESHOOTING.md)
- Open an issue on GitHub
