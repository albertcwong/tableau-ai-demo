#!/bin/sh
# Symlink .env from main worktree. Run once when using a manual worktree (git worktree add).
# Cursor worktrees use .cursor/worktrees.json instead.
set -e
MAIN_ROOT=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
if [ ! -f "$MAIN_ROOT/.env" ]; then
  echo "Error: $MAIN_ROOT/.env not found. Create it from .env.example in the main worktree." >&2
  exit 1
fi
ln -sf "$MAIN_ROOT/.env" .env
ln -sf "$MAIN_ROOT/frontend/localhost-key.pem" frontend/localhost-key.pem
ln -sf "$MAIN_ROOT/frontend/localhost.pem" frontend/localhost.pem
echo "CERT_PATH=$MAIN_ROOT/frontend" > .env.worktree
echo "Linked .env and frontend certs from $MAIN_ROOT"
echo "For Docker: docker compose --env-file .env --env-file .env.worktree -f docker-compose.yml -f docker-compose.dev.yml up -d"
