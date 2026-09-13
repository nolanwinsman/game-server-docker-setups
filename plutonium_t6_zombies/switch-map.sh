#!/bin/bash
#
# switch-map.sh (RCON version)
#
# Interactive menu to switch the map on a running aio-plutonium-t6 Zombies
# server, using RCON. Unlike the docker-exec/screen approach, this works from
# ANY machine on the network (or over Tailscale) - no SSH or Docker access to
# the host required. Requires `nc` (netcat) to be installed.
#
# Usage:
#   ./switch-map.sh
#
# Configuration: fill in SERVER_IP and SERVER_PORT below, or override at
# runtime with environment variables:
#   SERVER_IP=100.65.180.117 SERVER_PORT=4976 ./switch-map.sh
#
# The RCON password is read from (in order of priority):
#   1. RCON_PASSWORD environment variable
#   2. SERVER_RCON_PASSWORD in a .env file next to this script (matches the
#      docker-compose .env naming, so you can reuse the same file)
#   3. Prompted interactively (hidden input)

set -e

# ---- Configuration ----
SERVER_IP="${SERVER_IP:-100.65.180.117}"   # Tailscale or LAN IP of the server
SERVER_PORT="${SERVER_PORT:-4976}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
# ------------------------

# Map menu: label|execgts_config|map_codename
# Add more rows here (Survival/Grief/Turned variants, etc.) as needed.
MAPS=(
    "TranZit (Classic)|zm_classic_transit.cfg|zm_transit"
    "Die Rise (Classic)|zm_classic_rooftop.cfg|zm_highrise"
    "Mob of the Dead (Classic)|zm_classic_prison.cfg|zm_prison"
    "Buried (Classic)|zm_classic_processing.cfg|zm_buried"
    "Origins (Classic)|zm_classic_tomb.cfg|zm_tomb"
    "Nuketown Zombies (Standard)|zm_standard_nuked.cfg|zm_nuked"
)

# ---- Check dependencies ----
if ! command -v nc &> /dev/null; then
    echo "ERROR: 'nc' (netcat) is required but not installed."
    echo "Install it with: sudo apt install netcat-openbsd   (Debian/Ubuntu)"
    echo "                 sudo pacman -S openbsd-netcat      (Arch)"
    exit 1
fi

# ---- Resolve RCON password ----
if [ -z "$RCON_PASSWORD" ] && [ -f "$ENV_FILE" ]; then
    RCON_PASSWORD=$(grep -E '^SERVER_RCON_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2-)
fi

if [ -z "$RCON_PASSWORD" ]; then
    read -rsp "RCON password for ${SERVER_IP}:${SERVER_PORT}: " RCON_PASSWORD
    echo ""
fi

if [ -z "$RCON_PASSWORD" ]; then
    echo "ERROR: No RCON password provided."
    exit 1
fi

# ---- RCON send function ----
# T6 uses the Quake3-style RCON protocol: a UDP packet prefixed with four
# 0xFF bytes, followed by "rcon <password> <command>".
send_rcon() {
    local cmd="$1"
    printf '\xff\xff\xff\xffrcon %s %s\n' "$RCON_PASSWORD" "$cmd" \
        | nc -u -w2 "$SERVER_IP" "$SERVER_PORT"
}

# ---- Menu ----
echo "=========================================="
echo " Plutonium T6 Zombies - Map Switcher (RCON)"
echo "=========================================="
echo " Target: ${SERVER_IP}:${SERVER_PORT}"
echo ""

for i in "${!MAPS[@]}"; do
    IFS="|" read -r label _ _ <<< "${MAPS[$i]}"
    printf "  %d) %s\n" "$((i + 1))" "$label"
done

echo ""
read -rp "Choose a map [1-${#MAPS[@]}]: " choice

# Validate input is a number within range
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#MAPS[@]}" ]; then
    echo "Invalid choice: '$choice'. Please enter a number between 1 and ${#MAPS[@]}."
    exit 1
fi

index=$((choice - 1))
IFS="|" read -r label gametype_cfg map_codename <<< "${MAPS[$index]}"

echo ""
echo "Switching to: ${label}"
echo "Command: execgts ${gametype_cfg} map ${map_codename}"
echo ""

response=$(send_rcon "execgts ${gametype_cfg} map ${map_codename}")

if [ -z "$response" ]; then
    echo "No response received from server."
    echo "This could mean: wrong IP/port, server unreachable, or a firewall blocking UDP."
elif echo "$response" | grep -qi "bad rconpassword\|rconpassword.*invalid"; then
    echo "ERROR: RCON authentication failed - check your password."
else
    echo "Server response:"
    echo "$response"
fi

echo ""
echo "If the map changed successfully, give it a few seconds to load fastfiles."
