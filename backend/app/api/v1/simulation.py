"""Simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.simulation import (
    CommandRequest,
    CommandResponse,
    ValidationResponse,
)
from ...schemas.topology import TopologySchema
from ...simulation.commands import COMMAND_SETS
from ...simulation.runner import run_command
from ...simulation.validation import validate_topology

router = APIRouter(tags=["simulation"])


@router.post("/simulate/command", response_model=CommandResponse)
def simulate_command(request: CommandRequest) -> CommandResponse:
    """Run one terminal command against a topology.

    The topology travels with the request, so the backend holds no session
    state. The response carries the terminal output, the ordered event trace
    that drives the packet animation, inspector records for every frame that
    crossed a wire, and the learned tables to write back into the document.
    """
    return run_command(request.topology, request.device_id, request.command)


@router.post("/topology/validate", response_model=ValidationResponse)
def validate(topology: TopologySchema) -> ValidationResponse:
    """Report configuration mistakes that need no traffic to detect."""
    return validate_topology(topology)


@router.get("/commands")
def list_commands() -> dict[str, list[dict[str, str]]]:
    """Command reference per device type, used by the terminal's help panel."""
    return {
        kind: [
            {"name": c.name, "usage": c.usage or c.name, "summary": c.summary}
            for c in sorted(command_set.commands, key=lambda c: c.name)
        ]
        for kind, command_set in COMMAND_SETS.items()
    }
