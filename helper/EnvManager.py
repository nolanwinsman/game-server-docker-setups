import os


class EnvManager:
    def __init__(self, path=".env"):
        self.path = path
        self.env = self._load()
        self.dirty = False

    def _load(self):
        env = {}

        if not os.path.exists(self.path):
            return env

        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

        return env

    # --------------------------------------------------
    # CORE: REQUIRE VALUE
    # --------------------------------------------------
    def require(self, key, prompt=None, optional=False):
        """
        Ensures an environment variable exists and is non-empty.
        Empty strings (KEY=) are treated as missing.
        """

        raw = self.env.get(key, None)
        value = raw.strip() if isinstance(raw, str) else ""

        # already valid
        if value != "":
            self._print_masked(key, value)
            return value

        # missing
        prompt_text = f"{prompt or key}"
        if optional:
            prompt_text += " (optional)"

        print(f"{prompt_text}:", end=" ")
        value = input().strip()

        self.env[key] = value
        self.dirty = True
        return value

    # --------------------------------------------------
    # PRINT HELPERS (UNIFIED)
    # --------------------------------------------------
    def _print_masked(self, key, value):
        """Print env value safely (mask secrets)."""

        if self._is_secret(key):
            print(f"{key} = {self._mask(value)}")
        else:
            print(f"{key} = {value}")

    def _is_secret(self, key):
        return any(x in key.upper() for x in ["TOKEN", "KEY", "SECRET"])

    def _mask(self, value):
        if not value:
            return "***"
        if len(value) <= 10:
            return "***"
        return value[:6] + "..." + value[-4:]

    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------
    def summary(self):
        if not self.env:
            print("No .env values found.")
            return

        print("\nLoaded environment variables:")

        for k, v in self.env.items():
            self._print_masked(k, v)

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------
    def save(self):
        if not self.dirty:
            return

        with open(self.path, "w") as f:
            for k, v in self.env.items():
                f.write(f"{k}={v}\n")

        self.dirty = False