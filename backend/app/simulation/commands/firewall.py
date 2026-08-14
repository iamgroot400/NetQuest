"""Commands available on a firewall."""

from __future__ import annotations

from ..transport.segment import TransportProtocol
from ..transport.services import describe_port
from .common import show_interfaces
from .registry import Command, CommandContext, CommandResult, CommandSet


def cmd_show_rules(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    rules = getattr(device, "rules", [])
    hits = getattr(device, "hits", {})
    policy = getattr(device, "default_policy", "allow")

    lines = [
        f"Firewall rules on {device.name}",
        "",
        "  #  Action  Protocol  Port            Source           Destination      Hits",
        "  -  ------  --------  --------------  ---------------  ---------------  ----",
    ]

    if not rules:
        lines.append("  (no rules configured)")
    else:
        for index, rule in enumerate(rules):
            protocol = (rule.protocol or "any").lower()
            if rule.port is not None and protocol in ("tcp", "udp"):
                port = describe_port(
                    TransportProtocol.TCP if protocol == "tcp" else TransportProtocol.UDP,
                    rule.port,
                )
            else:
                port = "any"
            lines.append(
                f"  {index + 1:<2} {rule.action:<7} {protocol:<9} {port:<15} "
                f"{(rule.source or 'any'):<16} {(rule.destination or 'any'):<16} "
                f"{hits.get(str(index), 0)}"
            )
            if rule.description:
                lines.append(f"       └─ {rule.description}")

    lines.append("")
    lines.append(
        f"  Default policy: {policy}  "
        f"(matched {hits.get('default', 0)} time(s))"
    )
    lines.append("")
    lines.append("Rules are evaluated top to bottom and the first match wins.")
    return CommandResult(output=lines)


def cmd_show_interfaces(ctx: CommandContext) -> CommandResult:
    return CommandResult(output=show_interfaces(ctx.network, ctx.device))


def cmd_clear_counters(ctx: CommandContext) -> CommandResult:
    hits = getattr(ctx.device, "hits", None)
    if hits is None:
        return CommandResult(output=["This device has no counters."], success=False)
    total = sum(hits.values())
    hits.clear()
    return CommandResult(output=[f"Cleared {total} counted packet(s)."])


def cmd_help(ctx: CommandContext) -> CommandResult:
    return CommandResult(
        output=[
            f"Available commands on {ctx.device.name}:",
            "",
            *FIREWALL_COMMANDS.help_lines(),
        ]
    )


FIREWALL_COMMANDS = CommandSet(
    [
        Command(
            name="show access-list",
            summary="List the rules, in evaluation order, with hit counts",
            handler=cmd_show_rules,
        ),
        Command(
            name="show firewall",
            summary="Alias of show access-list",
            handler=cmd_show_rules,
        ),
        Command(
            name="show interfaces",
            summary="Show which segment each side is attached to",
            handler=cmd_show_interfaces,
        ),
        Command(
            name="clear counters",
            summary="Reset the per-rule hit counters",
            handler=cmd_clear_counters,
        ),
        Command(name="help", summary="List available commands", handler=cmd_help),
        Command(
            name="clear",
            summary="Clear the terminal screen",
            handler=lambda ctx: CommandResult(output=[]),
        ),
    ]
)
