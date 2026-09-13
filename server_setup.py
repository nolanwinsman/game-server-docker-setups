import os
import subprocess


# -----------------------------
# Helpers
# -----------------------------
def run(cmd):
    subprocess.run(cmd, check=True)


def user_exists(username):
    return subprocess.run(
        ["id", username],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0


def group_exists(groupname):
    return subprocess.run(
        ["getent", "group", groupname],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0


def get_uid(username):
    try:
        return int(subprocess.check_output(["id", "-u", username]).decode().strip())
    except subprocess.CalledProcessError:
        return None


def uid_in_use(uid):
    return subprocess.run(
        ["getent", "passwd", str(uid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0


def find_free_uid(preferred_uid):
    uid = preferred_uid
    while uid_in_use(uid):
        uid += 1
    return uid


# -----------------------------
# User / Group Management
# -----------------------------
def ensure_user(username, uid):
    current_uid = get_uid(username)

    if current_uid is not None:
        if current_uid == uid:
            print(f"[SKIP] user '{username}' already exists (uid {uid})")
            return

        print(f"[MIGRATE] UID change {current_uid} → {uid}")
        run(["sudo", "usermod", "-u", str(uid), username])
        return

    target_uid = uid
    if uid_in_use(uid):
        target_uid = find_free_uid(uid)
        print(f"[WARN] UID {uid} is already in use by another user; using {target_uid} instead")

    print(f"[CREATE] user '{username}' (uid {target_uid})")
    run(["sudo", "useradd", "-u", str(target_uid), username])


def ensure_group(groupname, gid):
    existing = subprocess.run(
        ["getent", "group", str(gid)],
        capture_output=True,
        text=True
    ).stdout.strip()

    if existing:
        name = existing.split(":")[0]

        if name != groupname:
            raise Exception(f"GID {gid} already used by '{name}'")

        print(f"[SKIP] group '{groupname}' exists")
        run(["sudo", "groupmod", "-g", str(gid), groupname])

    else:
        print(f"[CREATE] group '{groupname}' (gid {gid})")
        run(["sudo", "groupadd", "-g", str(gid), groupname])


# -----------------------------
# Main Class
# -----------------------------
class GameServerSetup:
    """
    Creates the groups, users and folder structure a game server container
    needs on the host (mirrors EZarr's UserGroupSetup pattern).

    Every game gets a method named after its folder under game-server-setups/
    (e.g. `plutonium_t6_zombies`). Add a new method here when adding a new game.
    """

    def __init__(self, root_dir):
        self.root_dir = root_dir

        ensure_group("game-servers", 13500)
        run(["sudo", "usermod", "-a", "-G", "game-servers", os.getenv("USER")])

        # media_read / media_write are EZarr groups; on hosts without EZarr
        # they don't exist and that's fine, we don't depend on them.

    def plutonium_t6_zombies(self):
        ensure_user("plutonium-t6", 13501)

        base = f"{self.root_dir}/aio-plutonium-t6"

        dirs = [
            "plutonium",
            "server",
            "server_data",
            "admin",
            "updater",
            "downloaded_files",
            "status",
        ]

        for d in dirs:
            run(["sudo", "mkdir", "-pv", "-m", "775", f"{base}/{d}"])

        # Raw merged game files (base game + DLCs) live here; drop them in
        # before first `docker compose up`, it is mounted read-only at /t6server/game_files.
        run(["sudo", "mkdir", "-pv", "-m", "775", f"{base}/server/pluto_t6_full_game"])

        run(["sudo", "chown", "-R", "plutonium-t6:game-servers", base])

        print(f"[INFO] Drop your merged game files (base + DLCs) into: {base}/server/pluto_t6_full_game")