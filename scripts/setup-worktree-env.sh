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
echo "Linked .env -> $MAIN_ROOT/.env"
