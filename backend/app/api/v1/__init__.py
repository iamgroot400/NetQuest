"""Version 1 of the NetQuest API."""

from fastapi import APIRouter

from . import challenges, simulation

router = APIRouter()
router.include_router(simulation.router)
router.include_router(challenges.router)


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


__all__ = ["router"]
