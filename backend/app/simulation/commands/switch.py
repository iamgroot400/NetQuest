"""Commands available on a Layer 2 switch."""

from __future__ import annotations

from .common import show_interfaces
from .registry import Command, CommandContext, CommandResult, CommandSet


def cmd_show_mac_table(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    table = getattr(device, "mac_table", {})

    lines = [
        "          MAC Address Table",
        "------------------------------------------",
        " MAC Address          Type       Port",
        " -----------          ----       ----",
    ]
    if not table:
        lines.append("")
        lines.append(" The table is empty. A switch only learns an address once it")
        lines.append(" has seen a frame arrive from it — send some traffic first.")
        return CommandResult(output=lines)

    for mac in sorted(table):
        iface = device.interface(table[mac])
        port = iface.name if iface else "unknown"
        lines.append(f" {mac.ljust(20)} DYNAMIC    {port}")

    lines.append("")
    lines.append(f"Total entries: {len(table)}")
    return CommandResult(output=lines)


def cmd_clear_mac_table(ctx: CommandContext) -> CommandResult:
    table = getattr(ctx.device, "mac_table", None)
    if table is None:
        return CommandResult(output=["This device has no MAC address table."], success=False)
    count = len(table)
    table.clear()
    return CommandResult(output=[f"Cleared {count} dynamic entries."])


def cmd_show_interfaces(ctx: CommandContext) -> CommandResult:
    return CommandResult(output=show_interfaces(ctx.network, ctx.device))


def cmd_help(ctx: CommandContext) -> CommandResult:
    return CommandResult(
        output=[f"Available commands on {ctx.device.name}:", "", *SWITCH_COMMANDS.help_lines()]
    )


SWITCH_COMMANDS = CommandSet(
    [
        Command(
            name="show mac-address-table",
            summary="List the MAC addresses this switch has learned",
            handler=cmd_show_mac_table,
        ),
        Command(
            name="clear mac-address-table",
            summary="Forget every learned MAC address",
            handler=cmd_clear_mac_table,
        ),
        Command(
            name="show interfaces",
            summary="Show port status and what is plugged into each one",
            handler=cmd_show_interfaces,
        ),
        Command(name="help", summary="List available commands", handler=cmd_help),
        Command(
            name="clear",
            summary="Clear the terminal screen",
            handler=lambda ctx: CommandResult(output=[]),
        ),
    ]
)
