#!/usr/bin/env python3
#
# switch-map.py - Plutonium T6 Zombies map switcher (RCON)
#
# Switches maps on a running aio-plutonium-t6 server. Works from any machine
# that can reach the server (LAN or Tailscale). Pure Python (stdlib) - no
# netcat required.
#
# Usage:
#   ./switch-map.sh        (from the helper/ folder - or call switch-map.sh from anywhere)
#
# Config (any of):
#   - SERVER_IP / SERVER_PORT env vars
#   - .env at the repo root (shared by every game's docker-compose and reused here):
#       SERVER_IP=...
#       SERVER_PORT=4976
#       SERVER_RCON_PASSWORD=...
#       EXTRA_MAPS=[{"label":"My Modded Map","gametype":"zm_my_mod.cfg","map":"zm_my_map"}]
#       MAPS_FILE=/abs/path/to/maps.json
#   - maps.json / maps.yaml next to this script (see maps.example.json)
#
# Map entries support:
#   {"label": "...", "gametype": "zm_classic_tomb.cfg", "map": "zm_tomb"}
#   {"label": "...", "command": "gametype zclassic loc transit map zm_transit"}  # full override

import json
import os
import socket
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(SCRIPT_DIR)          # helper/ -> game folder
ENV_FILE = os.path.join(GAME_DIR, "..", ".env")  # shared repo-root .env

DEFAULT_MAPS = [
    {"label": "TranZit (Classic)", "gametype": "zm_classic_transit.cfg", "map": "zm_transit"},
    {"label": "Die Rise (Classic)", "gametype": "zm_classic_rooftop.cfg", "map": "zm_highrise"},
    {"label": "Mob of the Dead (Classic)", "gametype": "zm_classic_prison.cfg", "map": "zm_prison"},
    {"label": "Buried (Classic)", "gametype": "zm_classic_processing.cfg", "map": "zm_buried"},
    {"label": "Origins (Classic)", "gametype": "zm_classic_tomb.cfg", "map": "zm_tomb"},
    {"label": "Nuketown Zombies (Standard)", "gametype": "zm_standard_nuked.cfg", "map": "zm_nuked"},
]


# ---------------------------------------------------------------------------
# .env + map loading
# ---------------------------------------------------------------------------
def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if " #" in v:
                    v = v.split(" #", 1)[0].strip()
                env[k] = v
    return env


def normalize_maps(data):
    if isinstance(data, dict):
        data = data.get("maps", data.get("extras", []))
    out = []
    for m in data or []:
        if not isinstance(m, dict):
            continue
        label = m.get("label")
        if not label:
            label = m.get("map") or m.get("gametype") or "Unnamed"
        out.append(m)
    return out


def load_maps_file(path):
    if not os.path.exists(path):
        return []
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            print(f"NOTE: {path} is YAML but PyYAML is not installed.")
            print("      Install it with: python3 -m pip install pyyaml")
            print("      ...or convert to JSON (maps.json) which needs no dependencies.")
            return []
        return normalize_maps(yaml.safe_load(open(path)))
    return normalize_maps(json.load(open(path)))


def gather_maps(env):
    maps = list(DEFAULT_MAPS)

    # 1) maps.json / maps.yaml sitting next to this script
    for cand in ("maps.json", "maps.yaml", "maps.yml"):
        path = os.path.join(SCRIPT_DIR, cand)
        if os.path.exists(path):
            maps.extend(load_maps_file(path))

    # 2) MAPS_FILE in .env / envvars (absolute path, can be a URL later)
    maps_file = env.get("MAPS_FILE") or os.environ.get("MAPS_FILE", "")
    if maps_file:
        maps.extend(load_maps_file(maps_file))

    # 3) EXTRA_MAPS in .env / envvars (inline JSON array)
    extra = env.get("EXTRA_MAPS") or os.environ.get("EXTRA_MAPS", "")
    if extra:
        try:
            maps.extend(normalize_maps(json.loads(extra)))
        except json.JSONDecodeError as e:
            print(f"WARNING: EXTRA_MAPS is not valid JSON, ignoring ({e})")

    seen = set()
    dedup = []
    for m in maps:
        key = map_command(m)
        if key not in seen:
            seen.add(key)
            dedup.append(m)
    return dedup


def map_command(m):
    if m.get("command"):
        return m["command"]
    return f"execgts {m['gametype']} map {m['map']}"


# ---------------------------------------------------------------------------
# RCON clients
# ---------------------------------------------------------------------------
def q3_rcon(ip, port, password, cmd, iw_trailer, timeout=2.0):
    """Quake3-style RCON over UDP.

    Classic payload:  \xff\xff\xff\xff rcon <pass> <cmd>\n
    IW engine variant (used by T6/Plutonium): trailing \x00\xe6\xea
    """
    tail = b"\x00\xe6\xea" if iw_trailer else b"\n"
    payload = b"\xff\xff\xff\xffrcon " + password.encode() + b" " + cmd.encode() + tail
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, (ip, port))
        data, _ = s.recvfrom(65535)
        return data.decode("latin-1", "replace")
    except socket.timeout:
        return None
    finally:
        s.close()


class SourceRCON:
    """Source RCON protocol over TCP (the SRCDS-style handshake)."""

    P_AUTH = 3
    P_EXEC = 2
    P_AUTH_RESP = 2  # same value as EXECCOMMAND; that's the Valve protocol
    P_RESP = 0

    def __init__(self, ip, port, password, timeout=5.0):
        self.timeout = timeout
        self._password = password
        self.sock = socket.create_connection((ip, port), timeout=timeout)
        self.sock.settimeout(timeout)

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("connection closed by server")
            buf += chunk
        return buf

    def _send(self, pid, ptype, body):
        body = body.encode("utf-8")
        payload = struct.pack("<ii", pid, ptype) + body + b"\x00"
        self.sock.sendall(struct.pack("<i", len(payload)))
        self.sock.sendall(payload)

    def _read(self):
        size = struct.unpack("<i", self._recv_exact(4))[0]
        data = self._recv_exact(size)
        pid, ptype = struct.unpack("<ii", data[:8])
        body = data[8:]
        if body.endswith(b"\x00"):
            body = body[:-1]
        return pid, ptype, body

    def authenticate(self):
        self._send(0, self.P_AUTH, self._password)
        for _ in range(5):
            try:
                _pid, ptype, body = self._read()
            except (socket.timeout, EOFError):
                return False
            if ptype == self.P_AUTH_RESP:
                return body == b"0"
        return False

    def exec_command(self, cmd):
        self._send(1, self.P_EXEC, cmd)
        out = []
        while True:
            try:
                _pid, ptype, body = self._read()
            except (socket.timeout, EOFError):
                break
            if ptype == self.P_RESP and body == b"":
                break
            if ptype == self.P_RESP:
                out.append(body.decode("utf-8", "replace"))
        return "\n".join(out)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def rcon_send(ip, port, password, cmd):
    """Try Source RCON (TCP) then Quake3 UDP variants.

    Returns (ok: bool, message: str, method: str).
    """
    # 1) Source RCON over TCP (what IW4M-Admin and most tools speak).
    try:
        src = SourceRCON(ip, port, password)
        try:
            if not src.authenticate():
                return (False, "RCON authentication failed - check SERVER_RCON_PASSWORD.", "Source RCON (TCP)")
            reply = src.exec_command(cmd)
            if reply.strip():
                return (True, reply, "Source RCON (TCP)")
            return (True, "command sent; no textual response (this is normal for map swaps).", "Source RCON (TCP)")
        finally:
            src.close()
    except socket.timeout:
        pass
    except ConnectionRefusedError:
        pass
    except (OSError, ValueError, EOFError, struct.error) as e:
        pass

    # 2) Quake3-style UDP, IW engine trailer (Plutonium's native variant).
    for iw_trailer, name in ((True, "Q3/UDP (IW trailer)"), (False, "Q3/UDP (classic)")):
        resp = q3_rcon(ip, port, password, cmd, iw_trailer=iw_trailer)
        if resp is not None:
            if "bad rconpassword" in resp.lower() or "no rcon password" in resp.lower():
                return (False, "RCON authentication failed - check SERVER_RCON_PASSWORD.", name)
            return (True, resp, name)

    return (None, "No response from the server on UDP.\n"
                 "  Possible causes:\n"
                 "   1. The container is down, or the port map changed (check `docker ps`).\n"
                 "   2. A firewall is dropping UDP {port} to the server host.\n"
                 "   3. The game server is running but RCON is disabled (empty rcon_password).".format(port=port), "UDP")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    env = load_env()

    ip = os.environ.get("SERVER_IP") or env.get("SERVER_IP") or "100.65.180.117"
    port = int(os.environ.get("SERVER_PORT") or env.get("SERVER_PORT") or "4976")
    password = os.environ.get("RCON_PASSWORD") or env.get("SERVER_RCON_PASSWORD") or ""

    maps = gather_maps(env)
    if not maps:
        print("ERROR: no maps found (built-ins failed to load).")
        sys.exit(1)

    print("==========================================")
    print(" Plutonium T6 Zombies - Map Switcher (RCON)")
    print("==========================================")
    print(f" Target: {ip}:{port}")
    print("")

    for i, m in enumerate(maps):
        print(f"  {i + 1:>2}) {m.get('label', 'Unnamed')}")
    print("   q) Exit")

    print("")
    while True:
        choice = input(f"Choose a map [1-{len(maps)}]: ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("Goodbye.")
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(maps):
            break
        print(f"Invalid choice: '{choice}'. Enter 1-{len(maps)} or 'q'.")

    m = maps[int(choice) - 1]
    cmd = map_command(m)

    print("")
    print(f"Switching to: {m.get('label')}")
    print(f"Command: {cmd}")
    print("")

    ok, msg, method = rcon_send(ip, port, password, cmd)

    if ok is None:
        print(f"[{method}] {msg}")
    elif ok:
        print(f"[{method}] OK. Server response:")
        print(msg)
    else:
        print(f"[{method}] ERROR: {msg}")

    print("")
    print("If the map changed successfully, give it a few seconds to load fastfiles.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)