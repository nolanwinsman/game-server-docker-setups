# Plutonium T6 Zombies — RCON admin

Two ways to manage the running server with RCON: the **IW4MAdmin web console**
(bundled with the container, the recommended route) or the **in-game console**.
No scripts needed.

## The container's admin tool: IW4MAdmin webfront

The aio-plutonium-t6 image bundles [IW4MAdmin](https://github.com/RaidMax/IW4M-Admin/wiki/Getting-Started)
(RaidMax's server admin tool) and publishes its web console at
`http://<host>:1624` (matches `ADMIN_PORT` in the repo-root `.env`). Use this
first — Plutonium's own devs say the in-game `/rcon` command can be unreliable
and recommend an external tool like this.

- **First-run setup**: enter the game and type `!owner` in chat (claims
  ownership), then `!rt` to get the initial web-UI login. Afterwards complete
  the config wizard:
  `docker exec -it plutonium bash -c "screen -r admin-panel"`, then detach
  with `Ctrl+A` then `Ctrl+D`.
- **Server entry in the wizard**: IP `127.0.0.1`, Port `4976`
  (`SERVER_PORT` / `net_port`), Password = `SERVER_RCON_PASSWORD` (default
  `admin`). Set both **RCon parser** and **Event parser** to
  **`Plutonium T6 Parser (2024)`** — they must match each other and the game
  ([Configuration wiki](https://github.com/RaidMax/IW4M-Admin/wiki/Configuration#parser-names)).
- **RCON for Plutonium T6 runs over UDP on the game port** (4976), not TCP.
  IW4MAdmin reaches the server at `127.0.0.1:4976/udp` inside the container,
  so nothing extra needs forwarding. The compose block's `4976/tcp` line is not
  used by RCON.
- If you ever run IW4MAdmin from another host (not `127.0.0.1`), whitelist its
  IP in the server cfg: `rconWhitelistAdd "<ip>"` ([FAQ](https://github.com/RaidMax/IW4M-Admin/wiki/FAQ)).
- The panel polls the server every 5 s by default (`RConPollRate`), on top of
  the watchdog's own RCON probe — RCON is (lightly) hammered constantly, so
  still send map-switch commands one at a time.

The web console runs the exact same commands as below, just without the `/rcon`
prefix.

## In-game console route

Manage the server from inside the game client — no SSH, Docker, or scripts
needed. Open the console in the game and talk to the server over RCON.

## RCON login

1. Launch Plutonium and join your server (find it in the server list, or use
   `connect <ip>:4976` in the console).
2. Press **`~`** (tilde) to open the console. You can also open it / get back to it
   while playing.
3. Log in with the server's RCON password:

   ```
   /rcon login <password>
   ```

   The password is `SERVER_RCON_PASSWORD` from the repo-root `.env`
   (`example.env:18`). If you left it blank during setup, the default is **`admin`**.

   If `rcon login` succeeds but `rcon` commands print nothing, RCON output is
   suppressed by default. Run:

   ```
   /rcon con_displayRconOutput 1
   ```

   then re-run `/rcon status`. To keep it enabled across server restarts, add
   `con_displayRconOutput 1` to the server config
   `/mnt/ssd/config/aio-plutonium-t6/server/Zombie/main/dedicated_zm.cfg`.

4. Verify the login worked:

   ```
   /rcon status
   ```

   This prints the running map and every connected player.

Notes:

- The leading `/` is optional — `rcon login admin` works too.
- Commands **must** have `rcon` in front of them. Without it you execute the
  command on *your own client*, not the server (e.g. `map zm_transit` locally
  yanks you into a private match instead of switching the server).
- Login persists until you leave the server.

## Changing maps

Zombies maps need the right game-type settings loaded (rounds, layout, perks).
The `.cfg` files in the server's `gamesettings/` folder hold those settings, and
the config names are `zm_<gametype>_<location>.cfg`. Always switch to a map using
its matching config.

> **Take it slow.** Send one map-switch command, then wait for the map to finish
> loading before issuing another. Firing rapid RCON/map commands mid-transition
> is a known way to crash a T6 server. If the server ever stops answering (RCON
> goes silent, server still "listed"), the container's watchdog
> (`resources/server-launch.sh`) auto-restarts it after 2 missed probes.

### Reliable method (uses the server's own rotation)

Set the rotation to exactly one map, then rotate:

```
/rcon sv_maprotation "execgts zm_classic_transit.cfg map zm_transit"
/rcon map_rotate
```

This is exactly what the server does on startup (`sv_maprotation` in
`dedicated_zm.cfg`), so it always works — including when players are in game.

### Direct method

```
/rcon execgts zm_classic_transit.cfg
/rcon map zm_transit
```

If `execgts` is not recognized on your build, `exec` works as the fallback:

```
/rcon exec zm_classic_transit.cfg
/rcon map zm_transit
```

## Map reference

Stock maps, using the configs shipped with the server (from `dedicated_zm.cfg`):

| Map / mode | RCON commands |
|---|---|
| TranZit (Classic) | `/rcon execgts zm_classic_transit.cfg` then `/rcon map zm_transit` |
| TranZit Farm / Town / Bus Depot (Survival) | `zm_standard_farm.cfg` / `zm_standard_town.cfg` / `zm_standard_transit.cfg` → `map zm_transit` |
| TranZit Farm / Town / Bus Depot (Grief) | `zm_grief_farm.cfg` / `zm_grief_town.cfg` / `zm_grief_transit.cfg` → `map zm_transit` |
| TranZit Diner (Turned) | `zm_cleansed_diner.cfg` → `map zm_transit_dr` |
| Die Rise (Classic) | `zm_classic_rooftop.cfg` → `map zm_highrise` |
| Mob of the Dead (Classic) | `zm_classic_prison.cfg` → `map zm_prison` |
| Mob of the Dead (Grief) | `zm_grief_cellblock.cfg` → `map zm_prison` |
| Buried (Classic) | `zm_classic_processing.cfg` → `map zm_buried` |
| Buried (Turned) | `zm_cleansed_street.cfg` → `map zm_buried` |
| Buried (Grief) | `zm_grief_street.cfg` → `map zm_buried` |
| Origins (Classic) | `zm_classic_tomb.cfg` → `map zm_tomb` |
| Nuketown (Standard) | `zm_standard_nuked.cfg` → `map zm_nuked` |

DLC maps (Buried, Origins, Nuketown) only load if the DLC zone files exist in the
server's game files.

### Adding a custom / modded map

1. Put the map's `.cfg` (matching the `zm_*_*.cfg` format) in the server's
   `gamesettings/` folder, and the map itself in the server's game files.
2. Restart the server or reload the settings so the new config is available.
3. Use the rotation method with your config:

   ```
   /rcon sv_maprotation "execgts <your-gametype>.cfg map <your_map>"
   /rcon map_rotate
   ```

## Other useful admin commands

Handy once logged in (all prefixed with `rcon`):

| Command | What it does |
|---|---|
| `/rcon status` | Current map + player list |
| `/rcon map_restart` | Restart the current map |
| `/rcon fast_restart` | Restart the current match instantly |
| `/rcon say <text>` | Broadcast a message to all players |
| `/rcon clientkick <id>` | Kick a player by client id (from `status`) |
| `/rcon cmdlist` | List all engine commands |
| `/rcon dvarlist` | List all dvars |

## Troubleshooting

- **"Unknown command"** — the server won't run the command; you left off `rcon`
  (executing locally) or the command doesn't exist. Prefix with `/rcon`.
- **Login fails** — wrong `SERVER_RCON_PASSWORD`, or a non-default password was
  set after the server started. The server only reads it once at boot (first-time
  setup `sed`s it into `dedicated_zm.cfg`), so changing `.env` requires a
  container restart.
- **Nothing happens after a map command** — the map config didn't match the map
  (`execgts zm_classic_tomb.cfg` + `map zm_prison` breaks the load). Use the
  rotation method, which is stricter.
- **Map saying/Moves need the right dvar** — the game-type `.cfg` *must* be
  executed before the `map` command or zombies can fail to spawn.
- **Commands run but print nothing** — RCON output display is off by default.
  Run `/rcon con_displayRconOutput 1`, then re-run your command.
- **RCON replies not showing in console** — output is off by default in some
  builds; run `/rcon con_displayRconOutput 1`.