"""Entry point the API calls: run one command against one topology."""

from __future__ import annotations

from ..schemas.simulation import (
    CommandResponse,
    DeviceStateSchema,
    PacketSchema,
    SimEventSchema,
)
from ..schemas.topology import TopologySchema
from .commands import execute
from .core.engine import SimulationEngine
from .loader import build_network, collect_state


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
