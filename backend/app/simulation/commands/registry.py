"""Command dispatch.

Each device type exposes a `CommandSet`. Commands may be several words long
(`show mac-address-table`), so resolution matches the longest registered name
against the leading tokens of the input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine
    from ..core.network import Network
    from ..devices.base import Device


@dataclass
class CommandContext:
    device: "Device"
    network: "Network"
    engine: "SimulationEngine"
    args: list[str]
    raw: str


@dataclass
class CommandResult:
    output: list[str] = field(default_factory=list)
    success: bool = True


Handler = Callable[[CommandContext], CommandResult]


@dataclass
class Command:
    name: str
    summary: str
    handler: Handler
    usage: str = ""

    @property
    def tokens(self) -> list[str]:
        return self.name.split()


class CommandSet:
    def __init__(self, commands: list[Command]) -> None:
        # Longest first so `show ip route` wins over a hypothetical `show`.
        self.commands = sorted(commands, key=lambda c: -len(c.tokens))

    def resolve(self, tokens: list[str]) -> tuple[Command, list[str]] | None:
        lowered = [t.lower() for t in tokens]
        for command in self.commands:
            n = len(command.tokens)
            if lowered[:n] == command.tokens:
                return command, tokens[n:]
        return None

    def help_lines(self) -> list[str]:
        width = max((len(c.usage or c.name) for c in self.commands), default=0)
        return [
            f"  {(c.usage or c.name).ljust(width)}   {c.summary}"
            for c in sorted(self.commands, key=lambda c: c.name)
        ]
