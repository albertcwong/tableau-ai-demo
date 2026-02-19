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
    [ -f .env ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env"
    [ -f .env.worktree ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env.worktree"
    docker compose $COMPOSE_ARGS down --remove-orphans
    exit 0
    ;;
esac

# Load .env.worktree first (manual worktrees)
CERT_ROOT="${PROJECT_ROOT}"
[ -f .env.worktree ] && set -a && . ./.env.worktree && set +a

# Cert path: prefer repo root shared/ (matches worktrees.json), else worktree shared
REPO_ROOT=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")" 2>/dev/null && pwd)
if [ -d "${REPO_ROOT}/shared" ] && [ -f "${REPO_ROOT}/shared/localhost-key.pem" ]; then
  SHARED_CERT="${REPO_ROOT}/shared"
elif [ -d "${CERT_ROOT}/shared" ] && [ -f "${CERT_ROOT}/shared/localhost-key.pem" ]; then
  SHARED_CERT="${CERT_ROOT}/shared"
else
  SHARED_CERT="${CERT_ROOT}/../shared"
fi
if [ -f "${SHARED_CERT}/localhost-key.pem" ] && [ -f "${SHARED_CERT}/localhost.pem" ]; then
  export CERT_PATH="${SHARED_CERT}"
elif [ -z "${CERT_PATH}" ]; then
  export CERT_PATH="${CERT_ROOT}/frontend"
fi

COMPOSE_ARGS="-f docker-compose.yml -f docker-compose.dev.yml"
[ -f .env ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env"
[ -f .env.worktree ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file .env.worktree"
[ $# -eq 0 ] && set -- up

if [ "${1}" = "up" ]; then
  shift
  docker compose $COMPOSE_ARGS up --remove-orphans "$@"
else
  docker compose $COMPOSE_ARGS "$@"
fi
[ "${1:-up}" = "up" ] && echo "Frontend: https://localhost:${FRONTEND_HTTPS_PORT}" && echo "Backend:  http://localhost:${BACKEND_PORT}"
