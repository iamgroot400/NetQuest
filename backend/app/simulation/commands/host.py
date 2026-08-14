"""Commands available on PCs and servers."""

from __future__ import annotations

from ..core.addressing import is_valid_ipv4
from ..icmp.message import ECHO_PAYLOAD_BYTES
from .ping import run_ping
from .registry import Command, CommandContext, CommandResult, CommandSet
from .tools import (
    cmd_connect,
    cmd_curl,
    cmd_dhcp,
    cmd_dig,
    cmd_ip,
    cmd_netstat,
    cmd_nslookup,
    cmd_services,
    cmd_traceroute,
)

NOT_SET = "(not configured)"


def cmd_ipconfig(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    verbose = any(a.lower() in ("/all", "-all", "all") for a in ctx.args)
    lines = [f"{device.name} — IP Configuration", ""]

    if not device.interfaces:
        lines.append("   This device has no network adapters.")
        return CommandResult(output=lines, success=False)

    gateway = device.config.gateway or NOT_SET
    dns_server = device.config.dns_server or NOT_SET
    lease = getattr(device, "dhcp_lease", None)

    for iface in device.interfaces:
        state = "" if iface.enabled else "  [administratively down]"
        lines.append(f"Ethernet adapter {iface.name}:{state}")
        if verbose:
            lines.append(
                f"   DHCP Enabled. . . . . . . . . . . : "
                f"{'Yes' if device.config.dhcp_client else 'No'}"
            )
        lines.append(f"   IPv4 Address. . . . . . . . . . . : {iface.ipv4 or NOT_SET}")
        lines.append(f"   Subnet Mask . . . . . . . . . . . : {iface.netmask or NOT_SET}")
        lines.append(f"   Default Gateway . . . . . . . . . : {gateway}")
        lines.append(f"   DNS Server. . . . . . . . . . . . : {dns_server}")
        lines.append(f"   Physical Address. . . . . . . . . : {iface.mac}")
        if verbose and lease is not None:
            lines.append(
                f"   DHCP Server . . . . . . . . . . . : {lease.server_ip or NOT_SET}"
            )
            lines.append(
                f"   Lease Time. . . . . . . . . . . . : {lease.lease_seconds} seconds"
            )
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


def cmd_dnscache(ctx: CommandContext) -> CommandResult:
    cache = getattr(ctx.device, "dns_cache", {})
    if not cache:
        return CommandResult(
            output=[
                "The DNS cache is empty.",
                "Resolve a name with nslookup or ping and it will appear here.",
            ]
        )
    lines = ["Cached name resolutions", "", "Name                            Address"]
    for name in sorted(cache):
        lines.append(f"{name:<31} {cache[name]}")
    return CommandResult(output=lines)


def cmd_ping(ctx: CommandContext) -> CommandResult:
    return run_ping(ctx)


def cmd_help(ctx: CommandContext) -> CommandResult:
    lines = [f"Available commands on {ctx.device.name}:", ""]
    lines.extend(HOST_COMMANDS.help_lines())
    return CommandResult(output=lines)


HOST_COMMANDS = CommandSet(
    [
        Command(
            name="ipconfig",
            summary="Show address, mask, gateway, DNS and MAC; /all adds lease detail",
            usage="ipconfig [/all]",
            handler=cmd_ipconfig,
        ),
        Command(
            name="ping",
            summary=f"Send {ECHO_PAYLOAD_BYTES}-byte ICMP echo requests to an address or name",
            usage="ping <ip|name> [-n count]",
            handler=cmd_ping,
        ),
        Command(
            name="traceroute",
            summary="Show every router a packet passes through on its way there",
            usage="traceroute <ip|name>",
            handler=cmd_traceroute,
        ),
        Command(
            name="tracert",
            summary="Alias of traceroute",
            usage="tracert <ip|name>",
            handler=cmd_traceroute,
        ),
        Command(
            name="nslookup",
            summary="Ask the configured DNS server to resolve a name",
            usage="nslookup <name>",
            handler=cmd_nslookup,
        ),
        Command(
            name="dig",
            summary="Detailed DNS lookup, showing the full record chain",
            usage="dig <name> [A|CNAME|MX]",
            handler=cmd_dig,
        ),
        Command(
            name="connect",
            summary="Test whether a TCP or UDP port actually accepts traffic",
            usage="connect <ip|name> <port> [udp]",
            handler=cmd_connect,
        ),
        Command(
            name="curl",
            summary="Test a web service the way a browser would reach it",
            usage="curl http://host[:port]",
            handler=cmd_curl,
        ),
        Command(
            name="arp",
            summary="Show the ARP cache; -d clears it",
            usage="arp [-d [ip]]",
            handler=cmd_arp,
        ),
        Command(
            name="ip",
            summary="Show interfaces or routes",
            usage="ip addr | ip route",
            handler=cmd_ip,
        ),
        Command(
            name="netstat",
            summary="List the ports this device is listening on",
            handler=cmd_netstat,
        ),
        Command(
            name="ss",
            summary="Alias of netstat",
            handler=cmd_netstat,
        ),
        Command(
            name="services",
            summary="Show every service this device can run and its state",
            handler=cmd_services,
        ),
        Command(
            name="dhcp",
            summary="Obtain or give up an address over DHCP",
            usage="dhcp [renew|release]",
            handler=cmd_dhcp,
        ),
        Command(
            name="dns-cache",
            summary="Show names this host has already resolved",
            handler=cmd_dnscache,
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
