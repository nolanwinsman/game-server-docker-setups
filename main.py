import os
import subprocess
from container_configs import GameContainerConfig
from server_setup import GameServerSetup
from helper.EnvManager import EnvManager

# Each entry: folder name -> friendly display name. The folder must contain the
# game's supporting files (its docker-compose.yml gets generated into it).
# Adding a new game server = add one line here + a matching method in
# container_configs.py and server_setup.py.
GAMES = {
    "plutonium_t6_zombies": "Plutonium T6 Zombies",
}

ALL_YES = False


def take_boolean_input(default=True):
    if ALL_YES:
        return True

    while True:
        ans = input()
        if ans == '':
            return default
        if ans == 'y' or ans == 'Y':
            return True
        if ans == 'n' or ans == 'N':
            return False
        print('Please answer with y or n.', end=' ')


def take_directory_input(default_path):
    while True:
        ans = input()
        if ans == '':
            print(f"Defaulted to {default_path}")
            return default_path
        if ans[0] == '/':
            if ans[-1] == '/':
                return ans[:-1]
            return ans
        print('Please make sure the path is absolute, meaning it starts at the root of your filesystem and starts with "/":', end=' ')


def env_default(env, key, value):
    if not env.env.get(key):
        env.env[key] = value
        env.dirty = True
        print(f"{key} = {value}")


ENV_CONFIG = dict()


def configure_plutonium_t6_zombies_env(env):
    env.require("SERVER_MODE", prompt="Server mode (Zombie/Multiplayer)", optional=True)

    LAN_MODE = env.require("LAN_MODE", prompt="Run in LAN mode? (true/false)", optional=True)
    if not LAN_MODE or LAN_MODE.lower() not in ("true", "false"):
        print("Defaulting LAN_MODE to false")
        env_default(env, "LAN_MODE", "false")
        LAN_MODE = "false"

    if LAN_MODE.lower() == "false":
        env.require("SERVER_KEY", prompt="Server key (get one from https://plutonium.pw)")
        env.require("SERVER_RCON_PASSWORD", prompt="RCON password (blank = default 'admin')", optional=True)
        env.require("SERVER_PASSWORD", prompt="Server password (blank = none)", optional=True)

    env.require("SERVER_MAX_CLIENTS", prompt="Max clients, 1-8 (blank = default 4)", optional=True)

    default = env_default
    if not env.env.get("SERVER_PORT"):
        env_default(env, "SERVER_PORT", "4976")
    if not env.env.get("ADMIN_PORT"):
        env_default(env, "ADMIN_PORT", "1624")


ENV_CONFIG['plutonium_t6_zombies'] = configure_plutonium_t6_zombies_env


print('Welcome to the Game Server Setup CLI.')
print('This CLI will ask which game servers you\'d like to set up and then generate their docker-compose.yml, '
      '.env and on-host folder/groups.')

print('Default YES to everything? [Y/n]', end=" ")
ALL_YES = take_boolean_input()

print('\n===GAME SERVERS===')
requested = []
for game_dir, game_name in GAMES.items():
    print(f'Setup {game_name}? [Y/n]', end=" ")
    if take_boolean_input():
        requested.append(game_dir)
    else:
        print(f'Not adding {game_name}.')
if len(requested) == 0:
    print('No game servers selected. Terminating.')
    exit(1)

print('\n===CONFIGURATION===')
print('Where would you like to keep your game server config files? (defaults to /mnt/ssd/config)', end=" ")
root_dir = take_directory_input('/mnt/ssd/config')

for game_dir in requested:
    game_name = GAMES[game_dir]
    print(f'\n===SETTING UP {game_name}===')
    env = EnvManager(os.path.join(game_dir, '.env'))

    print('Create/update the .env file for this game server? [Y/n]', end=" ")
    if take_boolean_input():
        ENV_CONFIG[game_dir](env)
    else:
        print('Skipping .env file. Make sure the variables exist or docker compose will warn.')

    with open(os.path.join(game_dir, 'docker-compose.yml'), 'w') as compose:
        container_config = GameContainerConfig(root_dir)
        compose.write(getattr(container_config, game_dir)())
    print("docker-compose.yml generated successfully.")

    print('Create the required groups, users and folder structure (required for first time setup) [Y/n]: ', end=" ")
    if take_boolean_input():
        try:
            server_setup = GameServerSetup(root_dir)
            getattr(server_setup, game_dir)()
        except subprocess.CalledProcessError:
            print(f"Error: host setup failed for '{game_name}'. Continuing...")
    else:
        print("Group/user/folder creation skipped by user.")

    if env.dirty:
        print("Updates made to .env file. Saving updates.")
        env.save()

print('\nProcess complete! To start your servers:')
for game_dir in requested:
    print(f'  cd {game_dir} && docker compose up -d')
print('\nHelper scripts:')
print('  plutonium_t6_zombies/switch-map.sh   - interactive T6 Zombies map switcher (RCON)')
print('Thank you for using the Game Server Setup CLI. If you experience any issues, open an issue.')
exit(0)