#!/bin/bash
# Pull the latest images and redeploy the containers.
#
# For the private Plutonium image this only gets you the latest ghcr build -
# push the rebuild in the aio-plutonium-t6 repo first (Actions -> "Run workflow").
# One-time GHCR login is required on each host, see docs/docker-registry-login.md.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Pulling latest images"
docker compose pull

echo "==> Recreating containers with the new images"
docker compose up -d

echo "==> Done. Check the containers with: docker compose ps"