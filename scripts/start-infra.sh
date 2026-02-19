#!/bin/sh
# Start Postgres and Redis (shared infra). Run from repo root.
# Creates .env.infra so dev-docker uses postgres/redis (container-to-container on tableau-demo-net).
# Usage: ./scripts/start-infra.sh [up -d|down|...]
cd "$(dirname "$0")/.."
[ $# -eq 0 ] && set -- up -d
docker compose -f docker-compose.infra.yml -p tableau-demo-infra "$@"
if [ "$1" = "up" ] && [ "${2:-}" != "down" ]; then
  {
    echo "DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tableau_demo"
    echo "REDIS_URL=redis://redis:6379/0"
  } > .env.infra
  echo "Created .env.infra (dev-docker will use postgres/redis)"
fi
