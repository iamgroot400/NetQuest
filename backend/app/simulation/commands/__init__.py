"""Command dispatch across device types."""

from __future__ import annotations

from ..core.engine import SimulationEngine
from ..core.network import Network
from ..devices.base import Device
from .host import HOST_COMMANDS
from .registry import Command, CommandContext, CommandResult, CommandSet
from .router import ROUTER_COMMANDS
from .switch import SWITCH_COMMANDS

#: Keyed by `Device.kind`. Register new device types here.
COMMAND_SETS: dict[str, CommandSet] = {
    "pc": HOST_COMMANDS,
    "server": HOST_COMMANDS,
    "switch": SWITCH_COMMANDS,
    "router": ROUTER_COMMANDS,
}


def command_set_for(device: Device) -> CommandSet:
    return COMMAND_SETS.get(device.kind, HOST_COMMANDS)


def execute(
    device: Device, network: Network, engine: SimulationEngine, raw: str
) -> CommandResult:
    tokens = raw.strip().split()
    if not tokens:
        return CommandResult(output=[])

    command_set = command_set_for(device)
    resolved = command_set.resolve(tokens)
    if resolved is None:
        return CommandResult(
            output=[
                f"'{raw.strip()}' is not recognised on {device.name}.",
                "Type 'help' to see what this device understands.",
            ],
            success=False,
        )

    command, args = resolved
    context = CommandContext(
        device=device, network=network, engine=engine, args=args, raw=raw
    )
    return command.handler(context)


__all__ = [
    "COMMAND_SETS",
    "Command",
    "CommandContext",
    "CommandResult",
    "CommandSet",
    "command_set_for",
    "execute",
]
