#!/bin/sh
set -e
cd /app
# Add Tableau cert to Python's CA bundle (Docker equivalent of Mac Keychain)
if [ -f /app/shared/server.crt ] && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
  cat /etc/ssl/certs/ca-certificates.crt /app/shared/server.crt > /tmp/ca-combined.pem
  export SSL_CERT_FILE=/tmp/ca-combined.pem
  export REQUESTS_CA_BUNDLE=/tmp/ca-combined.pem
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
