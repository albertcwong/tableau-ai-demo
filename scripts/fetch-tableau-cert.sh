#!/bin/sh
# Fetch Tableau server's SSL cert into shared/server.crt
# Usage: ./scripts/fetch-tableau-cert.sh [hostname]
# Example: ./scripts/fetch-tableau-cert.sh ec2-34-209-90-187.us-west-2.compute.amazonaws.com
set -e
HOST="${1:-ec2-34-209-90-187.us-west-2.compute.amazonaws.com}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")" 2>/dev/null && pwd)" || (cd "$SCRIPT_DIR/../.." && pwd)
SHARED="${REPO_ROOT}/shared"
OUT="${SHARED}/server.crt"
mkdir -p "$SHARED"
echo "Fetching cert from $HOST:443..."
echo | openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null | openssl x509 -outform PEM > "$OUT"
echo "Saved to $OUT"
openssl x509 -in "$OUT" -noout -subject -issuer
