# Pulling the private Plutonium image from GHCR

`ghcr.io/nolanwinsman/aio-plutonium-t6:latest` is a **private** container image.
`docker compose up -d` fails with `pull access denied` on any host that hasn't
logged in to the GitHub Container Registry yet.

## One-time login (per host)

Each new server needs the login once, as the user that will run docker:

```bash
echo '<PAT>' | docker login ghcr.io -u nolanwinsman --password-stdin
```

- `<PAT>` is a **Personal Access Token** created at
  GitHub → Settings → Developer settings → Personal access tokens.
- Classic token: scope **`read:packages`** (all you need to pull).
- Fine-grained token: **Packages: Read** on the `aio-plutonium-t6` package.
- Don't reuse a token that can write — read-only is enough for pulls.

## Verify

```bash
docker pull ghcr.io/nolanwinsman/aio-plutonium-t6:latest
docker compose up -d
```

The login lives in `~/.docker/config.json` (or the root user's, if sudo-ed
docker) and sticks around until you log out or the token is revoked.