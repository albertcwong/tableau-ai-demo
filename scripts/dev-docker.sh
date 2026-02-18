#!/bin/sh
# Start Docker dev stack with PWD-based dynamic ports (works from any worktree path).
# Usage: ./scripts/dev-docker.sh [up|down|url|...]
# Passes extra args to docker compose (e.g. -d for detached).
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# Deterministic ports from PWD - same path = same ports, different paths = no collision
HASH=$(echo -n "$PWD" | cksum 2>/dev/null | awk '{print $1}' || echo "0")
OFFSET=$((HASH % 1000))

export PROJECT_ROOT
export FRONTEND_HTTPS_PORT=$((3000 + OFFSET))
export FRONTEND_HTTP_PORT=$((3001 + OFFSET))
export BACKEND_PORT=$((8000 + OFFSET))
export COMPOSE_PROJECT_NAME="wt-${OFFSET}"

# URLs for frontend (agent discoverability)
export NEXT_PUBLIC_API_URL="http://localhost:${BACKEND_PORT}"
export APP_BASE_URL="https://localhost:${FRONTEND_HTTPS_PORT}"
export AUTH0_BASE_URL="https://localhost:${FRONTEND_HTTPS_PORT}"

case "${1:-up}" in
  url)
    echo "Frontend: https://localhost:${FRONTEND_HTTPS_PORT}"
    echo "Backend:  http://localhost:${BACKEND_PORT}"
    exit 0
    ;;
  down)
    COMPOSE_ARGS="-f docker-compose.yml -f docker-compose.dev.yml"
    [ -f .env.worktree ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env.worktree"
    docker compose $COMPOSE_ARGS down --remove-orphans
    exit 0
    ;;
esac

# Load .env.worktree (CERT_PATH, etc.) when present (manual worktrees)
COMPOSE_ARGS="-f docker-compose.yml -f docker-compose.dev.yml"
[ -f .env.worktree ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env.worktree"
[ $# -eq 0 ] && set -- up

if [ "${1}" = "up" ]; then
  shift
  docker compose $COMPOSE_ARGS up --remove-orphans "$@"
else
  docker compose $COMPOSE_ARGS "$@"
fi
[ "${1:-up}" = "up" ] && echo "Frontend: https://localhost:${FRONTEND_HTTPS_PORT}" && echo "Backend:  http://localhost:${BACKEND_PORT}"
