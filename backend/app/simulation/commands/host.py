"""Commands available on PCs and servers."""

from __future__ import annotations

from ..core.addressing import is_valid_ipv4, netmask_to_prefix
from ..icmp.message import ECHO_PAYLOAD_BYTES
from .ping import run_ping
from .registry import Command, CommandContext, CommandResult, CommandSet

NOT_SET = "(not configured)"


def cmd_ipconfig(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    lines = [f"{device.name} — IP Configuration", ""]

    if not device.interfaces:
        lines.append("   This device has no network adapters.")
        return CommandResult(output=lines, success=False)

    gateway = device.config.gateway or NOT_SET
    for iface in device.interfaces:
        state = "" if iface.enabled else "  [administratively down]"
        lines.append(f"Ethernet adapter {iface.name}:{state}")
        lines.append(f"   IPv4 Address. . . . . . . . . . . : {iface.ipv4 or NOT_SET}")
        lines.append(f"   Subnet Mask . . . . . . . . . . . : {iface.netmask or NOT_SET}")
        lines.append(f"   Default Gateway . . . . . . . . . : {gateway}")
        lines.append(f"   Physical Address. . . . . . . . . : {iface.mac}")
        lines.append("")

    return CommandResult(output=lines)


def cmd_arp(ctx: CommandContext) -> CommandResult:
    device = ctx.device

    if ctx.args and ctx.args[0].lower() in ("-d", "--delete"):
        if len(ctx.args) > 1:
            target = ctx.args[1]
            if device.arp_table.remove(target):
                return CommandResult(output=[f"Deleted ARP entry for {target}."])
            return CommandResult(
                output=[f"No ARP entry found for {target}."], success=False
            )
        device.arp_table.clear()
        return CommandResult(output=["ARP cache cleared."])

    entries = device.arp_table.entries
    if not entries:
        return CommandResult(output=["No ARP entries found."])

    primary = device.ip_interfaces[0].ipv4 if device.ip_interfaces else "unknown"
    lines = [
        f"Interface: {primary}",
        "  Internet Address      Physical Address      Type",
    ]
    for ip in sorted(entries, key=lambda v: tuple(int(p) for p in v.split("."))):
        entry = entries[ip]
        lines.append(f"  {ip.ljust(20)}  {entry.mac.ljust(20)}  {entry.kind}")
    return CommandResult(output=lines)


def cmd_ping(ctx: CommandContext) -> CommandResult:
    return run_ping(ctx)


def cmd_netstat(ctx: CommandContext) -> CommandResult:
    """Summarise this host's own view of the network."""
    device = ctx.device
    lines = [f"{device.name} — interface status", ""]
    for iface in device.interfaces:
        link = ctx.network.link_for(iface.id)
        if link is None:
            cable = "no cable"
        elif not link.is_up:
            cable = "cable disconnected"
        else:
            peer = ctx.network.peer_of(iface.id)
            cable = f"connected to {peer[0].name} {peer[1].name}" if peer else "dangling cable"
        prefix = (
            f"{iface.ipv4}/{netmask_to_prefix(iface.netmask)}"
            if iface.has_ip and iface.netmask
            else NOT_SET
        )
        lines.append(f"  {iface.name}  {iface.status:<24} {prefix:<20} {cable}")
    return CommandResult(output=lines)


def cmd_help(ctx: CommandContext) -> CommandResult:
    lines = [f"Available commands on {ctx.device.name}:", ""]
    lines.extend(HOST_COMMANDS.help_lines())
    return CommandResult(output=lines)


HOST_COMMANDS = CommandSet(
    [
        Command(
            name="ipconfig",
            summary="Show this host's IP address, mask, gateway and MAC",
            handler=cmd_ipconfig,
        ),
        Command(
            name="ping",
            summary=f"Send {ECHO_PAYLOAD_BYTES}-byte ICMP echo requests to an address",
            usage="ping <ip> [-n count]",
            handler=cmd_ping,
        ),
        Command(
            name="arp",
            summary="Show the ARP cache; -d clears it",
            usage="arp [-d [ip]]",
            handler=cmd_arp,
        ),
        Command(
            name="netstat",
            summary="Show adapter status and what each cable is plugged into",
            handler=cmd_netstat,
        ),
        Command(name="help", summary="List available commands", handler=cmd_help),
        Command(
            name="clear",
            summary="Clear the terminal screen",
            handler=lambda ctx: CommandResult(output=[]),
        ),
    ]
)


def validate_ip_argument(value: str) -> str | None:
    """Return an error line when `value` is not a usable ping target."""
    if not is_valid_ipv4(value):
        return (
            f"Ping request could not find host {value}. "
            "Please check the name and try again."
        )
    return None
