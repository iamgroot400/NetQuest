"""Entry point the API calls: run one command against one topology."""

from __future__ import annotations

from ..schemas.simulation import (
    CommandResponse,
    ConnectionResponse,
    DeviceStateSchema,
    PacketSchema,
    SimEventSchema,
)
from ..schemas.topology import TopologySchema
from .commands import execute
from .connectivity import Outcome, attempt_connection
from .core.engine import SimulationEngine
from .devices.host import Host
from .loader import build_network, collect_state
from .transport.segment import TransportProtocol


def run_command(topology: TopologySchema, device_id: str, command: str) -> CommandResponse:
    network = build_network(topology)
    device = network.device(device_id)

    if device is None:
        return CommandResponse(
            output=[f"Device '{device_id}' is not part of this topology."],
            success=False,
        )

    engine = SimulationEngine(network)
    result = execute(device, network, engine, command)

    return CommandResponse(
        output=result.output,
        events=[SimEventSchema(**event.to_dict()) for event in engine.events],
        packets=[PacketSchema(**packet.to_dict()) for packet in engine.packets.values()],
        device_state={
            device_id: DeviceStateSchema(**state)
            for device_id, state in collect_state(network).items()
        },
        success=result.success,
    )


def run_connection_test(
    topology: TopologySchema,
    source_device_id: str,
    destination: str,
    port: int,
    protocol: str = "TCP",
) -> ConnectionResponse:
    """Open one connection and report where it got to.

    Backs the Connection Tester panel. Uses the same engine as the terminal, so
    the verdict cannot disagree with what `connect` would print.
    """
    network = build_network(topology)
    device = network.device(source_device_id)

    if device is None:
        return ConnectionResponse(
            reachable=False,
            outcome=Outcome.NO_ROUTE,
            detail=f"Device '{source_device_id}' is not part of this topology.",
            target=destination,
            port=port,
            protocol=protocol,
        )

    if not isinstance(device, Host):
        return ConnectionResponse(
            reachable=False,
            outcome=Outcome.NO_SOURCE_ADDRESS,
            detail=(
                f"{device.name} is a {device.kind} — connections have to start "
                "from a PC or a server."
            ),
            target=destination,
            port=port,
            protocol=protocol,
        )

    try:
        transport = TransportProtocol(protocol.upper())
    except ValueError:
        transport = TransportProtocol.TCP

    engine = SimulationEngine(network)
    attempt = attempt_connection(device, destination, port, engine, transport)

    return ConnectionResponse(
        reachable=attempt.reachable,
        outcome=attempt.outcome,
        detail=attempt.detail,
        target=attempt.target,
        resolved_ip=attempt.resolved_ip,
        port=attempt.port,
        protocol=attempt.protocol,
        path=attempt.path,
        blocked_at=attempt.blocked_at,
        blocked_reason=attempt.blocked_reason,
        dns_detail=attempt.dns_detail,
        events=[SimEventSchema(**event.to_dict()) for event in engine.events],
        packets=[PacketSchema(**packet.to_dict()) for packet in engine.packets.values()],
        device_state={
            device_id: DeviceStateSchema(**state)
            for device_id, state in collect_state(network).items()
        },
    )
