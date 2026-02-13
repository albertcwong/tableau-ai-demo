#!/bin/sh
set -e

# Create placeholder certificate files if they don't exist
# This allows docker-compose to start even without certificates
# The server will detect invalid certificates and fall back to HTTP
if [ ! -f /app/localhost-key.pem ]; then
  echo "Warning: localhost-key.pem not found, HTTPS will be disabled"
  touch /app/localhost-key.pem
fi

if [ ! -f /app/localhost.pem ]; then
  echo "Warning: localhost.pem not found, HTTPS will be disabled"
  touch /app/localhost.pem
fi

# Start the HTTPS wrapper server
exec node server-https.js
