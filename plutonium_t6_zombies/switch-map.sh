#!/bin/bash
#
# switch-map.sh - thin wrapper around switch-map.py
#
# Interactive menu to switch the map on a running aio-plutonium-t6 Zombies
# server over RCON. Works from ANY machine on the network (or over Tailscale);
# no SSH or Docker access to the host required. All logic lives in the
# companion Python script (switch-map.py), which needs no netcat.
#
# Usage:
#   ./switch-map.sh
#
# Configuration (see header of switch-map.py):
#   - SERVER_IP / SERVER_PORT env vars
#   - .env next to this script (SERVER_RCON_PASSWORD, EXTRA_MAPS, MAPS_FILE)
#   - maps.json / maps.yaml next to this script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/switch-map.py" ]; then
    echo "ERROR: switch-map.py not found next to this script."
    exit 1
fi

exec python3 "$SCRIPT_DIR/switch-map.py" "$@"