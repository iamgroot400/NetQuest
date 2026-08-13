"""Commands available on a router."""

from __future__ import annotations

from .common import show_interfaces
from .host import cmd_arp
from .ping import run_ping
from .registry import Command, CommandContext, CommandResult, CommandSet


def cmd_show_ip_route(ctx: CommandContext) -> CommandResult:
    table = getattr(ctx.device, "routing_table", None)
    routes = table.sorted_routes() if table else []

    lines = [
        "Codes: C - connected, S - static, S* - default route",
        "",
    ]
    if not routes:
        lines.append("No routes in the routing table.")
        lines.append("")
        lines.append("A router builds connected routes from its own interfaces:")
        lines.append("give an interface an IP address and mask, and a route appears.")
        return CommandResult(output=lines)

    for route in routes:
        network = f"{route.destination}/{route.prefix_length}"
        iface = ctx.device.interface(route.interface_id)
        port = iface.name if iface else "?"
        if route.gateway is None:
            lines.append(f"{route.code():<4} {network:<20} is directly connected, {port}")
        else:
            lines.append(f"{route.code():<4} {network:<20} via {route.gateway}, {port}")
    return CommandResult(output=lines)


def cmd_show_interfaces(ctx: CommandContext) -> CommandResult:
    return CommandResult(output=show_interfaces(ctx.network, ctx.device))


def cmd_show_arp(ctx: CommandContext) -> CommandResult:
    return cmd_arp(ctx)


def cmd_ping(ctx: CommandContext) -> CommandResult:
    return run_ping(ctx)


def cmd_help(ctx: CommandContext) -> CommandResult:
    return CommandResult(
        output=[f"Available commands on {ctx.device.name}:", "", *ROUTER_COMMANDS.help_lines()]
    )


ROUTER_COMMANDS = CommandSet(
    [
        Command(
            name="show ip route",
            summary="Show the routing table",
            handler=cmd_show_ip_route,
        ),
        Command(
            name="show interfaces",
            summary="Show interface addresses, status and cabling",
            handler=cmd_show_interfaces,
        ),
        Command(
            name="show arp",
            summary="Show the ARP cache",
            handler=cmd_show_arp,
        ),
        Command(
            name="ping",
            summary="Send ICMP echo requests from this router",
            usage="ping <ip> [-n count]",
            handler=cmd_ping,
        ),
        Command(name="help", summary="List available commands", handler=cmd_help),
        Command(
            name="clear",
            summary="Clear the terminal screen",
            handler=lambda ctx: CommandResult(output=[]),
        ),
    ]
)
