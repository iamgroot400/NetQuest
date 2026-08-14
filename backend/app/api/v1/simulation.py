"""Simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.simulation import (
    CommandRequest,
    CommandResponse,
    ConnectionRequest,
    ConnectionResponse,
    ValidationResponse,
)
from ...schemas.topology import TopologySchema
from ...simulation.commands import COMMAND_SETS
from ...simulation.runner import run_command, run_connection_test
from ...simulation.transport.services import WELL_KNOWN
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


@router.post("/simulate/connect", response_model=ConnectionResponse)
def simulate_connection(request: ConnectionRequest) -> ConnectionResponse:
    """Test whether one device can actually reach a port on another.

    Runs the same engine the terminal does, so the verdict, the hop path and
    the point where traffic stopped all come from real packets. The distinction
    between *refused* (the host said no) and *filtered* (something in between
    swallowed it) is preserved, because that is what tells a learner whether to
    look at the server or at the firewall.
    """
    return run_connection_test(
        request.topology,
        request.source_device_id,
        request.destination,
        request.port,
        request.protocol,
    )


@router.get("/services")
def list_services() -> list[dict[str, object]]:
    """The service catalogue the config panel offers as one-click ports."""
    return [
        {
            "name": service.name,
            "protocol": service.protocol.value,
            "port": service.port,
            "description": service.description,
        }
        for service in WELL_KNOWN
    ]


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
