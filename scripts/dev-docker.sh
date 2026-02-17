#!/bin/sh
# Start all services in Docker development mode (hot reload)
cd "$(dirname "$0")/.."
export PROJECT_ROOT=$(pwd)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up "$@"
