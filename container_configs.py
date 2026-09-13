import os


class GameContainerConfig:
    """
    Generates docker-compose.yml files for game servers, one file per game
    directory (mirrors EZarr's per-service container_configs pattern).

    Every game gets a method named after its folder under game-server-setups/
    (e.g. `plutonium_t6_zombies`). Add a new method here when adding a new game.

    The generated compose file reads secrets/tuning values from a .env file in
    the same directory via ${VARIABLE} substitution, exactly like EZarr.
    """

    def __init__(self, root_dir):
        self.root_dir = root_dir

    def plutonium_t6_zombies(self):
        cfg = f"{self.root_dir}/aio-plutonium-t6"
        return (
            "services:\n"
            "  aio-plutonium-t6:\n"
            "    image: ghcr.io/nolanwinsman/aio-plutonium-t6:latest\n"
            "    container_name: aio-plutonium-t6-server\n"
            "    restart: unless-stopped\n"
            "    ports:\n"
            '      - "4976:4976/udp"   # game server port (host:guest/udp) - must match SERVER_PORT\n'
            '      - "1624:1624/tcp"   # admin panel port (host:guest/tcp) - must match ADMIN_PORT\n'
            "    volumes:\n"
            f"      - {cfg}/plutonium:/t6server/plutonium\n"
            f"      - {cfg}/server/pluto_t6_full_game:/t6server/game_files:ro\n"
            f"      - {cfg}/server_data:/t6server/server\n"
            f"      - {cfg}/admin:/t6server/admin\n"
            f"      - {cfg}/updater:/t6server/updater\n"
            f"      - {cfg}/downloaded_files:/t6server/downloaded_files\n"
            f"      - {cfg}/status:/t6server/status\n"
            "    environment:\n"
            "      # --- Online mode settings ---\n"
            "      SERVER_KEY: \"${SERVER_KEY}\"                    # required for online mode, get it from https://plutonium.pw\n"
            "      LAN_MODE: \"${LAN_MODE}\"                        # set to \"true\" to run in LAN mode instead\n"
            "\n"
            "      # --- Common settings ---\n"
            "      SERVER_MODE: \"${SERVER_MODE}\"                  # \"Zombie\" or \"Multiplayer\"\n"
            "      SERVER_MAX_CLIENTS: \"${SERVER_MAX_CLIENTS}\"    # 1-8, leave blank for default (4)\n"
            "      SERVER_RCON_PASSWORD: \"${SERVER_RCON_PASSWORD}\" # leave blank for default (admin)\n"
            "      SERVER_PASSWORD: \"${SERVER_PASSWORD}\"          # leave blank for no password\n"
            "      SERVER_PORT: \"${SERVER_PORT}\"                  # must match the udp port mapping above\n"
            "      ADMIN_PORT: \"${ADMIN_PORT}\"                    # must match the tcp port mapping above\n"
            "\n"
            "      # --- LAN mode only (uncomment/set if LAN_MODE is \"true\") ---\n"
            "      # SERVER_MAP_ROTATION: \"${SERVER_MAP_ROTATION}\"\n"
        )