#!/usr/bin/env python3
"""Interactively pick the Zombies map the server loads at boot.

Edits SERVER_MAP_ROTATION in the repo-root .env (all other lines untouched),
then restart the container to apply. Run from the repo root:

    python helper/pick_zm_map.py

Picking 0 restores the server's default rotation.
"""

import os
import sys

# (label, gamesettings cfg, map) - from the server's own map reference
MAPS = [
    ("TranZit (Classic)", "zm_classic_transit.cfg", "zm_transit"),
    ("TranZit Farm Survival", "zm_standard_farm.cfg", "zm_transit"),
    ("TranZit Town Survival", "zm_standard_town.cfg", "zm_transit"),
    ("TranZit Bus Depot Survival", "zm_standard_transit.cfg", "zm_transit"),
    ("TranZit Farm Grief", "zm_grief_farm.cfg", "zm_transit"),
    ("TranZit Town Grief", "zm_grief_town.cfg", "zm_transit"),
    ("TranZit Bus Depot Grief", "zm_grief_transit.cfg", "zm_transit"),
    ("TranZit Diner (Turned)", "zm_cleansed_diner.cfg", "zm_transit_dr"),
    ("Die Rise (Classic)", "zm_classic_rooftop.cfg", "zm_highrise"),
    ("Mob of the Dead (Classic)", "zm_classic_prison.cfg", "zm_prison"),
    ("Mob of the Dead (Grief)", "zm_grief_cellblock.cfg", "zm_prison"),
    ("Buried (Classic)", "zm_classic_processing.cfg", "zm_buried"),
    ("Buried (Turned)", "zm_cleansed_street.cfg", "zm_buried"),
    ("Buried (Grief)", "zm_grief_street.cfg", "zm_buried"),
    ("Origins (Classic)", "zm_classic_tomb.cfg", "zm_tomb"),
    ("Nuketown (Standard)", "zm_standard_nuked.cfg", "zm_nuked"),
]

KEY = "SERVER_MAP_ROTATION"


def rotation(cfg, mapname):
    return f'sv_maprotation "execgts {cfg} map {mapname}"'


def current_value(env_path):
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith(KEY + "="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return None


def set_value(env_path, value):
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    out = []
    done = False
    for line in lines:
        if line.lstrip().startswith(KEY + "=") or line.lstrip().startswith("# " + KEY + "="):
            if value is None:
                out.append(f"# {KEY}=disabled (server's default rotation)\n")
            else:
                out.append(f"{KEY}={value}\n")
            done = True
        else:
            out.append(line)

    if not done and value is not None:
        if lines and not lines[-1].endswith("\n"):
            out.append("\n")
        out.append(f"\n# Hardcoded map (set by helper/pick_zm_map.py)\n{KEY}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(out)


def main():
    env_path = sys.argv[1] if len(sys.argv) > 1 else ".env"
    cur = current_value(env_path)

    print("Plutonium T6 Zombies - map the server loads at boot")
    print()
    if cur:
        print(f"Current: {cur}")
        print()
    print("  0] Restore the server's default rotation")
    for i, (label, _, _) in enumerate(MAPS, start=1):
        print(f"{i:>2}] {label}")
    print()

    try:
        choice = int(input("Pick a map [0-16] (Enter = restore default): ") or 0)
    except ValueError:
        sys.exit("Not a number.")
    if not (0 <= choice <= len(MAPS)):
        sys.exit("Selection out of range.")

    if choice == 0:
        value = None
        label = "server's default rotation"
    else:
        label, cfg, mapname = MAPS[choice - 1]
        value = rotation(cfg, mapname)

    set_value(env_path, value)
    print(f"\nSet SERVER_MAP_ROTATION to: {label}")
    print(f"Written to {env_path}.")
    print("Restart the container to apply:  docker compose restart plutonium")


if __name__ == "__main__":
    main()