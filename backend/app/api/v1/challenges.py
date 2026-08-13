"""Challenge endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...challenges import loader, validator
from ...schemas.challenge import (
    ChallengeSchema,
    ChallengeValidationRequest,
    ChallengeValidationResponse,
)

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("", response_model=list[ChallengeSchema])
def list_challenges() -> list[ChallengeSchema]:
    """Every challenge found under the challenges directory, in play order."""
    return loader.sorted_challenges()


@router.get("/{challenge_id}", response_model=ChallengeSchema)
def get_challenge(challenge_id: str) -> ChallengeSchema:
    challenge = loader.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"No challenge with id '{challenge_id}'")
    return challenge


@router.post("/{challenge_id}/validate", response_model=ChallengeValidationResponse)
def validate_challenge(
    challenge_id: str, request: ChallengeValidationRequest
) -> ChallengeValidationResponse:
    """Check a topology against a challenge's objectives.

    Connectivity objectives run the real engine, so a ping objective only
    passes when a packet genuinely completes the round trip.
    """
    challenge = loader.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"No challenge with id '{challenge_id}'")
    return validator.validate(challenge, request.topology)
