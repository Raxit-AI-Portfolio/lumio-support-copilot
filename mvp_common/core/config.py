"""Settings shared by mvp_adk and mvp_lc, read from mvp_common/.env and the environment."""

import os
from pathlib import Path

COMMON_DIR = Path(__file__).parent.parent
KB_DIR = COMMON_DIR / "data" / "kb"
INDEX_FILE = COMMON_DIR / "data" / "kb_index.json"
EMBED_DIMENSIONS = 768


def load_env_file() -> None:
    """Copy KEY=value lines from mvp_common/.env into the environment if not already set."""
    env_file = COMMON_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_setting(name: str, default: str = "") -> str:
    """Return one setting from the environment."""
    load_env_file()
    return os.environ.get(name, default)


SEED_DIR = COMMON_DIR / "data" / "seed"
DB_FILE = COMMON_DIR / "data" / "lumio.db"
