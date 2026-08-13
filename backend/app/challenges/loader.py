"""Load challenge definitions from disk.

Files are read once at import and cached. `reload()` exists so tests (and a
`--reload` dev server) can pick up newly added files without a restart.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from ..core.config import settings
from ..schemas.challenge import ChallengeSchema

logger = logging.getLogger(__name__)

_cache: dict[str, ChallengeSchema] | None = None


def load_from(directory: Path) -> dict[str, ChallengeSchema]:
    challenges: dict[str, ChallengeSchema] = {}
    if not directory.is_dir():
        logger.warning("Challenge directory %s does not exist", directory)
        return challenges

    for path in sorted(directory.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            challenge = ChallengeSchema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            # A broken contributed file must not take the whole app down.
            logger.error("Skipping invalid challenge file %s: %s", path, exc)
            continue

        if challenge.id in challenges:
            logger.error("Duplicate challenge id '%s' in %s — skipped", challenge.id, path)
            continue
        challenges[challenge.id] = challenge

    logger.info("Loaded %d challenges from %s", len(challenges), directory)
    return challenges


def all_challenges() -> dict[str, ChallengeSchema]:
    global _cache
    if _cache is None:
        _cache = load_from(settings.challenges_dir)
    return _cache


def reload() -> dict[str, ChallengeSchema]:
    global _cache
    _cache = None
    return all_challenges()


def get(challenge_id: str) -> ChallengeSchema | None:
    return all_challenges().get(challenge_id)


def sorted_challenges() -> list[ChallengeSchema]:
    """Ordered for display: by level, then difficulty, then name."""
    return sorted(
        all_challenges().values(),
        key=lambda c: (c.level, c.difficulty, c.name),
    )
