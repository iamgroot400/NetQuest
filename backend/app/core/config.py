"""Runtime configuration, read from the environment."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _challenges_dir() -> Path:
    """Where challenge JSON files live.

    Defaults to `<repo>/challenges` for local development; the container sets
    CHALLENGES_DIR to the mounted path.
    """
    configured = os.environ.get("CHALLENGES_DIR")
    if configured:
        return Path(configured)
    return REPO_ROOT / "challenges"


class Settings:
    app_name = "NetQuest API"
    version = "0.1.0"
    api_prefix = "/api/v1"

    def __init__(self) -> None:
        self.challenges_dir = _challenges_dir()
        # Vite's dev server runs outside the container and needs CORS; in
        # production nginx proxies /api so the origin matches and this is unused.
        raw_origins = os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        )
        self.cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]


settings = Settings()
