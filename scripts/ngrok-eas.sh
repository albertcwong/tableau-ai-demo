#!/bin/bash
# Expose backend for Tableau EAS (OAuth 2.0 Trust).
# Backend must be running on port 8000. Update .env BACKEND_API_URL with the ngrok URL.
set -e
echo "Starting ngrok for Tableau EAS (port 8000)..."
echo ""
echo "After ngrok starts:"
echo "  1. Copy the HTTPS URL (e.g. https://abc123.ngrok-free.app)"
echo "  2. Set BACKEND_API_URL=<url> in .env and restart backend"
echo "  3. Add <url>/api/v1/tableau-auth/oauth/callback to Auth0 Allowed Callback URLs"
echo "  4. Register <url> as EAS Issuer in Tableau (Settings > Connected Apps > OAuth 2.0 Trust)"
echo ""
ngrok http 8000
