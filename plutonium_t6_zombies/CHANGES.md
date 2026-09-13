# aio-plutonium-t6: Changes from Upstream

This documents everything changed from the original [thejcpalma/aio-plutonium-t6](https://github.com/thejcpalma/aio-plutonium-t6) setup to get a working Zombies dedicated server running via Docker Compose with locally-owned game files.

## Summary

The upstream image's `server-launch.sh` had **three separate, unrelated bugs** that combined to make the server unusable out of the box:

1. Dead download URL for pre-packaged server files
2. Missing directory assumption when using raw game files
3. Two invalid/incorrect Plutonium engine startup arguments (the actual "server not running a map" cause)

None of these were fixable via environment variables alone — they required replacing `server-launch.sh` entirely via a bind mount.

---

## 1. Dead download source → build from local game files

**Problem:** The original script downloads a pre-built `T6-Server.zip` from `https://vault.our-space.xyz/ATOM/T6-Server.zip`. That URL now returns `404 Not Found` — the file no longer exists at that host (confirmed via `wget` from two independent machines/networks, ruling out local DNS/network issues).

**Fix:** Rewrote the "Server Files Provisioning" section to build the same `Multiplayer/` + `Zombie/` + `zone/` layout the launcher expects, directly from the user's own legally-obtained game files (`pluto_t6_full_game` + merged DLCs), mounted read-only at `/t6server/game_files`.

- Copies game files into `Multiplayer/` and `Zombie/` mode folders
- Removes the per-mode `zone/` copy and replaces it with a single shared symlink (`/t6server/server/zone` → `$GAME_FILES_DIR/zone`) to avoid tripling disk usage on the large fastfile data
- Also removed the redundant step that copied "Plutonium" files out of the zip — `check_updater.sh` already fetches real Plutonium client binaries from Plutonium's own official update servers, making that step unnecessary

## 2. Missing `main/` folders

**Problem:** The raw game files folder (`pluto_t6_full_game`) does not ship with a `main/` subfolder at its root (unlike a typical Steam BO2 install). The script assumed `main/` would exist after copying game files, so the later step that copies `dedicated.cfg`/`dedicated_zm.cfg` into `Multiplayer/main/` and `Zombie/main/` silently failed — the destination directory didn't exist, `cp` failed, but the script never checked that specific command's exit code, so it touched the "success" flag file anyway.

**Fix:** Added explicit `mkdir -p ".../Multiplayer/main"` and `.../Zombie/main` after the zone folder is removed, so the destination always exists before the config-copy step runs later.

## 3. Map rotation never actually starts (the core bug)

**Problem:** The Plutonium bootstrapper startup command was:
```
... -dedicated $LAN +start_map_rotate +set key $SERVER_KEY +set net_port $SERVER_PORT +set sv_config $CFG
```

This has two separate mistakes, confirmed directly from the live engine console log (captured via a persistent `screen -Logfile`, since the interactive `screen` session's output disappears when the process exits/crashes):

- **`+start_map_rotate` is not a valid console command** in the current Plutonium build (`r5346`) — the engine logs `Unknown command "start_map_rotate"` and silently ignores it.
- **`+set sv_config $CFG` only sets a dvar to a filename string** — it does not actually load/execute that config file. The correct approach (confirmed against other working Plutonium dedicated server setups) is `+exec $CFG`, which genuinely loads the file's contents, including the `sv_maprotation` setting the map rotation depends on.

Without a valid `+exec` of the config file, `sv_mapRotation` stayed empty even though the config file itself had a correct, non-empty rotation string — so `map_rotate` (once it did run) had nothing to rotate to, producing the exact symptom reported: `'<ip>:4976' tried to connect to us but we are not running a map!`

**Fix:** Changed the startup command to:
```
... -dedicated $LAN +exec $CFG +map_rotate +set key $SERVER_KEY +set net_port $SERVER_PORT
```

## 4. Minor: symlink recreation bug on restart

**Problem:** `ln -sf /t6server/server/zone /t6server/server/Zombie/zone` (and the Multiplayer equivalent) runs on every container start, not just the first. On restarts, `Zombie/zone` already exists as a symlink pointing to a directory — `ln -sf` treats an existing symlink-to-directory as the directory itself, and tries to create the new link *inside* it (`Zombie/zone/zone`), which then fails against the read-only game files mount.

**Fix:** Changed both instances to `ln -sfn`, which correctly replaces the symlink itself rather than resolving into it. This didn't block server startup (the pre-existing correct symlink was left untouched on failure) but was cleaned up while in the area.

## 5. Diagnostic addition: persistent server log

**Added:** `screen -S plutonium-server -L -Logfile /t6server/status/plutonium-server.log -dm ...`

The interactive `screen` session's scrollback disappears the moment the underlying Wine/Plutonium process exits or crashes, making it impossible to see what happened right before a crash. Adding `-L -Logfile` makes `screen` tee all output to a persistent file on disk that survives process crashes and container restarts, which was essential to actually diagnosing bug #3 above.

---

## 6. Changing maps server-side (Zombies)

**Why plain `map <mapname>` is unreliable:** Zombies mode maps aren't just a map name — they also depend on `gametype` and `loc` (location/variant) dvars. Several DLC "maps" actually share the same underlying map file with different game modes layered on top (e.g. `zm_transit` is used by TranZit, Survival, and Grief — they're distinguished by `gametype`/`loc`, not by map name alone). Typing bare `map zm_buried` loads the map but may leave gametype/loc in a stale or default state left over from whatever was previously active, which is why it can behave "funky" — wrong HUD, wrong round rules, sometimes an outright failure to start properly.

**The correct way** mirrors exactly how `dedicated_zm.cfg`'s own `sv_maprotation` is written — using `execgts` (exec game type settings) before `map`:

```
execgts zm_classic_transit.cfg map zm_transit
```

Or the fully explicit form (equivalent, spelled out):
```
gametype zclassic loc transit map zm_transit
```

### Reference: DLC map codenames and their `execgts` config

| Map | Map codename | `execgts` config (Classic) |
|---|---|---|
| TranZit (base game) | `zm_transit` | `zm_classic_transit.cfg` |
| Die Rise (DLC 1) | `zm_highrise` | `zm_classic_rooftop.cfg` |
| Mob of the Dead (DLC 2) | `zm_prison` | `zm_classic_prison.cfg` |
| Buried (DLC 3) | `zm_buried` | `zm_classic_processing.cfg` |
| Origins (DLC 4) | `zm_tomb` | `zm_classic_tomb.cfg` |
| Nuketown Zombies | `zm_nuked` | `zm_standard_nuked.cfg` |

(Other gametype variants — Survival `zm_standard_*.cfg`, Grief `zm_grief_*.cfg`, Turned `zm_cleansed_*.cfg` — are listed commented-out inside `dedicated_zm.cfg` itself; uncomment the one you want as your default rotation, or use them ad-hoc as below.)

### Changing the map live, from the host

Inject the full command into the running server's console via `screen`, same as before but with the corrected syntax:

```bash
docker exec -it aio-plutonium-t6-server screen -S plutonium-server -X stuff "execgts zm_classic_processing.cfg map zm_buried$(printf \\r)"
```

Swap in any row from the table above to switch maps/modes on demand without restarting the container.

### Setting a permanent map rotation

Set `SERVER_MAP_ROTATION` in `.env` using the same `execgts ... map ...` syntax, chaining multiple entries for a full rotation:
```
SERVER_MAP_ROTATION=sv_maprotation "execgts zm_classic_transit.cfg map zm_transit execgts zm_classic_buried.cfg map zm_buried"
```
Then uncomment the corresponding line in `docker-compose.yml`. Note this only applies on a fresh setup — see the flag-clearing step in the original map-rotation notes if you've already started the server once before changing it.


- Split the single `/t6server/server` volume mount into:
  - `/t6server/game_files` (read-only) — the user's raw, merged game files
  - `/t6server/server` (writable) — the constructed `Multiplayer/`/`Zombie/`/`zone` layout, built fresh by the replacement script
- Added a bind mount for the replacement `server_launch.sh`, overriding the broken one baked into the image, without needing to rebuild/fork the image itself
- Moved all secrets/config (`SERVER_KEY`, passwords, etc.) into a `.env` file next to `docker-compose.yml`, referenced via `${VARIABLE}` substitution, instead of hardcoding them in the compose file

## Files in this delivery

- `server_launch.sh` — the fully patched replacement script (all fixes above applied)
- `docker-compose.yml` — updated with the new mount layout
- `.env` — example environment file (fill in your own `SERVER_KEY`/passwords)
