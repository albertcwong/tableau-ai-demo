#!/bin/sh
# Symlink .env and certs from shared/. Run once when using a manual worktree (git worktree add).
# Cursor worktrees use .cursor/worktrees.json instead.
set -e
PROJECT_ROOT=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd)
SHARED="$PROJECT_ROOT/shared"
if [ ! -f "$SHARED/.env" ]; then
  echo "Error: $SHARED/.env not found. Create it from .env.example." >&2
  exit 1
fi
ln -sf "$SHARED/.env" .env
ln -sf "$SHARED/localhost-key.pem" frontend/localhost-key.pem
ln -sf "$SHARED/localhost.pem" frontend/localhost.pem
{
  echo "CERT_PATH=$SHARED"
  echo "PROJECT_ROOT=$(pwd)"
  echo "COMPOSE_PROJECT_NAME=tableau-ai-demo-$(basename "$(pwd)")"
} > .env.worktree
echo "Linked .env and certs from $SHARED"
echo "For Docker: ./scripts/dev-docker.sh up -d"
