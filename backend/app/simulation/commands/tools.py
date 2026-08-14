"""Diagnostic tools available on hosts.

Simplified versions of the commands a real operator reaches for, all running
against the simulated network state. Nothing here invents a result: every one
of them sends real traffic or reads real configuration.
"""

from __future__ import annotations

from ..connectivity import Outcome, attempt_connection
from ..core.addressing import (
    is_valid_ipv4,
    netmask_to_prefix,
    network_address,
)
from ..devices import app_services
from ..dns.records import DnsRecordType
from ..icmp.message import ECHO_PAYLOAD_BYTES, IcmpMessage, IcmpType
from ..ipv4.packet import IPProtocol, IPv4Packet
from ..transport.segment import TransportProtocol
from ..transport.services import WELL_KNOWN, describe_port, lookup
from .common import line_protocol
from .registry import CommandContext, CommandResult

MAX_TRACEROUTE_HOPS = 12
NOT_SET = "(not configured)"


# -- name resolution ------------------------------------------------------


def cmd_nslookup(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=["Usage: nslookup <name>"], success=False)

    name = ctx.args[0]
    device = ctx.device
    server = device.config.dns_server

    if not is_valid_ipv4(server):
        return CommandResult(
            output=[
                "No DNS server is configured on this host.",
                "Set one in the configuration panel, or obtain it from DHCP.",
            ],
            success=False,
        )

    lines = [f"Server:  {server}", f"Address: {server}#53", ""]
    response = device.resolve_name(name, ctx.engine)

    if response is None:
        lines.append(f"** no response from {server} for {name}")
        lines.append("The query was sent but nothing came back. Check the path to")
        lines.append("the DNS server, and whether UDP/53 is being blocked.")
        return CommandResult(output=lines, success=False)

    if not response.ok:
        lines.append(f"** server can't find {name}: {response.status.value}")
        if response.detail:
            lines.append(f"   {response.detail}")
        return CommandResult(output=lines, success=False)

    for record in response.chain[:-1]:
        lines.append(f"{record.name}\tcanonical name = {record.value}")
    lines.append(f"Name:    {response.chain[-1].name if response.chain else name}")
    lines.append(f"Address: {response.address}")
    return CommandResult(output=lines)


def cmd_dig(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=["Usage: dig <name> [A|CNAME|MX]"], success=False)

    name = ctx.args[0]
    record_type = DnsRecordType.A
    if len(ctx.args) > 1:
        try:
            record_type = DnsRecordType(ctx.args[1].upper())
        except ValueError:
            return CommandResult(
                output=[f"Unknown record type '{ctx.args[1]}'. Try A, CNAME or MX."],
                success=False,
            )

    device = ctx.device
    server = device.config.dns_server
    lines = [f"; <<>> NetQuest dig <<>> {name} {record_type.value}", ""]

    if not is_valid_ipv4(server):
        lines.append(";; no DNS server configured on this host")
        return CommandResult(output=lines, success=False)

    response = device.resolve_name(name, ctx.engine, record_type)
    lines.append(";; QUESTION SECTION:")
    lines.append(f";{name}.\t\tIN\t{record_type.value}")
    lines.append("")

    if response is None:
        lines.append(";; connection timed out; no servers could be reached")
        return CommandResult(output=lines, success=False)

    if response.answers:
        lines.append(";; ANSWER SECTION:")
        for record in response.chain or response.answers:
            lines.append(record.display())
        lines.append("")

    lines.append(f";; SERVER: {server}#53")
    lines.append(f";; STATUS: {response.status.value}")
    if response.detail:
        lines.append(f";; NOTE: {response.detail}")
    return CommandResult(output=lines, success=response.ok)


# -- path discovery -------------------------------------------------------


def cmd_traceroute(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(output=["Usage: traceroute <ip or name>"], success=False)

    device = ctx.device
    engine = ctx.engine
    target = ctx.args[0]

    address, dns = device.resolve_target(target, engine)
    if address is None:
        detail = f"could not resolve {target}"
        if dns is not None:
            detail = f"DNS answered {dns.status.value} for {target}"
        return CommandResult(
            output=[f"traceroute: {detail}"], success=False
        )

    lines = [
        f"Tracing route to {target} [{address}]",
        f"over a maximum of {MAX_TRACEROUTE_HOPS} hops:",
        "",
    ]
    arrived = False

    for ttl in range(1, MAX_TRACEROUTE_HOPS + 1):
        device.icmp_inbox.clear()
        probe = IPv4Packet(
            src_ip=device.select_source_ip(address)
            or (device.ip_interfaces[0].ipv4 if device.ip_interfaces else "0.0.0.0"),
            dst_ip=address,
            protocol=IPProtocol.ICMP,
            payload=IcmpMessage(
                type=IcmpType.ECHO_REQUEST, identifier=ttl, sequence=ttl
            ),
            ttl=ttl,
            length=ECHO_PAYLOAD_BYTES,
        )
        emissions = device.send_ipv4(probe, engine)
        if not emissions:
            lines.append(f"{ttl:>3}  the packet could not leave {device.name}")
            break
        engine.run(device, emissions)

        reply = next(
            (
                (packet, icmp)
                for packet, icmp in device.icmp_inbox
                if icmp.type is IcmpType.ECHO_REPLY
            ),
            None,
        )
        if reply is not None:
            lines.append(f"{ttl:>3}  {reply[0].src_ip}")
            arrived = True
            break

        expired = next(
            (
                (packet, icmp)
                for packet, icmp in device.icmp_inbox
                if icmp.type is IcmpType.TIME_EXCEEDED
            ),
            None,
        )
        if expired is not None:
            lines.append(f"{ttl:>3}  {expired[0].src_ip}")
            continue

        unreachable = next(
            (
                (packet, icmp)
                for packet, icmp in device.icmp_inbox
                if icmp.is_error
            ),
            None,
        )
        if unreachable is not None:
            lines.append(
                f"{ttl:>3}  {unreachable[0].src_ip}  {unreachable[1].summary()}"
            )
            break

        lines.append(f"{ttl:>3}  *  request timed out")

    lines.append("")
    lines.append("Trace complete." if arrived else "Trace did not reach the destination.")
    return CommandResult(output=lines, success=arrived)


# -- connection testing ---------------------------------------------------


_OUTCOME_TEXT = {
    Outcome.OPEN: "open",
    Outcome.REFUSED: "closed (connection refused)",
    Outcome.FILTERED: "filtered (no response)",
    Outcome.UNREACHABLE: "unreachable",
    Outcome.NO_ROUTE: "no route from this host",
    Outcome.DNS_FAILURE: "name did not resolve",
    Outcome.NO_SOURCE_ADDRESS: "this host has no address",
}


def cmd_connect(ctx: CommandContext) -> CommandResult:
    if len(ctx.args) < 2:
        return CommandResult(
            output=[
                "Usage: connect <ip or name> <port> [udp]",
                "Example: connect web.netquest.local 80",
            ],
            success=False,
        )

    target = ctx.args[0]
    port_text = ctx.args[1]
    if not port_text.isdigit():
        service = lookup(port_text)
        if service is None:
            return CommandResult(
                output=[f"'{port_text}' is not a port number or a known service name."],
                success=False,
            )
        port = service.port
        protocol = service.protocol
    else:
        port = int(port_text)
        protocol = (
            TransportProtocol.UDP
            if any(a.lower() == "udp" for a in ctx.args[2:])
            else TransportProtocol.TCP
        )

    result = attempt_connection(ctx.device, target, port, ctx.engine, protocol)
    return CommandResult(output=_render_attempt(result), success=result.reachable)


def cmd_curl(ctx: CommandContext) -> CommandResult:
    if not ctx.args:
        return CommandResult(
            output=["Usage: curl http://host[:port]"], success=False
        )

    raw = ctx.args[0]
    scheme, _, rest = raw.partition("://")
    if not rest:
        scheme, rest = "http", raw
    host_part = rest.split("/", 1)[0]
    default_port = 443 if scheme.lower() == "https" else 80

    if ":" in host_part:
        host, _, port_text = host_part.partition(":")
        port = int(port_text) if port_text.isdigit() else default_port
    else:
        host, port = host_part, default_port

    result = attempt_connection(
        ctx.device, host, port, ctx.engine, TransportProtocol.TCP
    )
    lines = [f"* Trying {host} on {describe_port(TransportProtocol.TCP, port)}…"]
    if result.resolved_ip and result.resolved_ip != host:
        lines.append(f"* {host} resolved to {result.resolved_ip}")

    if result.reachable:
        lines.append(f"* Connected to {host} ({result.resolved_ip}) port {port}")
        lines.append("")
        lines.append(
            "The web service is reachable. NetQuest simulates the connection, "
            "not the page itself, so there is no HTML to show."
        )
        return CommandResult(output=lines)

    lines.append(f"curl: could not connect — {result.detail}")
    if result.blocked_at:
        lines.append(f"curl: traffic stopped at {result.blocked_at}")
    return CommandResult(output=lines, success=False)


def _render_attempt(result) -> list[str]:
    label = describe_port(
        TransportProtocol(result.protocol), result.port or 0
    )
    lines = [f"Testing {result.protocol} to {result.target} on {label}", ""]
    if result.resolved_ip and result.resolved_ip != result.target:
        lines.append(f"{result.target} resolved to {result.resolved_ip}")
    lines.append(f"Result: {_OUTCOME_TEXT.get(result.outcome, result.outcome)}")
    lines.append(f"        {result.detail}")
    if result.path:
        lines.append("")
        lines.append(f"Path:   {' → '.join(result.path)}")
    if result.blocked_at:
        lines.append(f"Stopped at: {result.blocked_at}")
    if result.blocked_reason:
        lines.append(f"        {result.blocked_reason}")
    return lines


# -- local state readouts -------------------------------------------------


def cmd_ip(ctx: CommandContext) -> CommandResult:
    """`ip addr` and `ip route`, the two subcommands worth having."""
    sub = ctx.args[0].lower() if ctx.args else "addr"

    if sub in ("addr", "address", "a"):
        return _ip_addr(ctx)
    if sub in ("route", "r"):
        return _ip_route(ctx)
    return CommandResult(
        output=[f"Unknown subcommand '{sub}'. Try 'ip addr' or 'ip route'."],
        success=False,
    )


def _ip_addr(ctx: CommandContext) -> CommandResult:
    lines: list[str] = []
    for index, iface in enumerate(ctx.device.interfaces, start=1):
        state, _ = line_protocol(ctx.network, iface)
        flags = "UP" if iface.enabled else "DOWN"
        lines.append(f"{index}: {iface.name}: <{flags},LOWER_{state.upper()}>")
        lines.append(f"    link/ether {iface.mac}")
        if iface.has_ip and iface.netmask:
            assert iface.ipv4
            lines.append(
                f"    inet {iface.ipv4}/{netmask_to_prefix(iface.netmask)} "
                f"scope global {iface.name}"
            )
        else:
            lines.append("    inet (none)")
    return CommandResult(output=lines or ["This device has no interfaces."])


def _ip_route(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    table = getattr(device, "routing_table", None)
    lines: list[str] = []

    if table is not None:
        for route in table.sorted_routes():
            iface = device.interface(route.interface_id)
            port = iface.name if iface else "?"
            if route.gateway is None:
                lines.append(
                    f"{route.destination}/{route.prefix_length} dev {port} scope link"
                )
            else:
                lines.append(
                    f"{route.destination}/{route.prefix_length} via {route.gateway} dev {port}"
                )
        return CommandResult(output=lines or ["No routes."])

    # A host has no routing table; it has connected subnets plus a gateway.
    for iface in device.ip_interfaces:
        assert iface.ipv4 and iface.netmask
        lines.append(
            f"{network_address(iface.ipv4, iface.netmask)}/"
            f"{netmask_to_prefix(iface.netmask)} dev {iface.name} scope link "
            f"src {iface.ipv4}"
        )
    gateway = device.config.gateway
    if gateway:
        lines.insert(0, f"default via {gateway}")
    return CommandResult(output=lines or ["No routes — this host has no address."])


def cmd_netstat(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    open_ports = getattr(device, "open_ports", [])

    lines = ["Active listening sockets", "", "Proto  Local Address           Service"]
    if not open_ports:
        lines.append("")
        lines.append("Nothing is listening on this device.")
        lines.append("Enable a service in the configuration panel to open a port.")
        return CommandResult(output=lines)

    address = device.ip_interfaces[0].ipv4 if device.ip_interfaces else "0.0.0.0"
    for protocol, port, name in sorted(open_ports, key=lambda item: item[1]):
        lines.append(f"{protocol:<6} {f'{address}:{port}':<23} {name}")
    lines.append("")
    lines.append(f"{len(open_ports)} port(s) open.")
    return CommandResult(output=lines)


def cmd_services(ctx: CommandContext) -> CommandResult:
    """Everything this device could run, and whether it currently is."""
    configured = {
        (s.protocol.upper(), s.port): s for s in ctx.device.config.services
    }
    lines = ["Service       Port      State", ""]
    for service in WELL_KNOWN:
        key = (service.protocol.value, service.port)
        existing = configured.get(key)
        if existing is None:
            state = "not configured"
        else:
            state = "listening" if existing.enabled else "disabled"
        lines.append(
            f"{service.name:<13} {f'{service.port}/{service.protocol.value.lower()}':<9} {state}"
        )
    return CommandResult(output=lines)


# -- DHCP client ----------------------------------------------------------


def cmd_dhcp(ctx: CommandContext) -> CommandResult:
    action = ctx.args[0].lower() if ctx.args else "renew"

    if action == "release":
        if app_services.release_dhcp_lease(ctx.device, ctx.engine):
            return CommandResult(output=["Lease released. This host now has no address."])
        return CommandResult(
            output=["There is no DHCP lease to release."], success=False
        )

    if action not in ("renew", "request"):
        return CommandResult(
            output=[f"Unknown action '{action}'. Try 'dhcp renew' or 'dhcp release'."],
            success=False,
        )

    lines = ["Requesting a lease over DHCP…", ""]
    lease = ctx.device.request_dhcp_lease(ctx.engine)
    if lease is None:
        lines.append("DHCP request failed. No usable lease was offered.")
        lines.append("")
        lines.append("Check that a DHCP server is reachable on this segment, that its")
        lines.append("pool is enabled, and that it still has free addresses.")
        return CommandResult(output=lines, success=False)

    lines.append(f"Lease obtained from {lease.server_ip or 'the DHCP server'}")
    lines.append(f"   IPv4 Address. . . . . . . . . . . : {lease.ip}")
    lines.append(f"   Subnet Mask . . . . . . . . . . . : {lease.netmask}")
    lines.append(f"   Default Gateway . . . . . . . . . : {lease.gateway or NOT_SET}")
    lines.append(f"   DNS Server. . . . . . . . . . . . : {lease.dns or NOT_SET}")
    lines.append(f"   Lease Time. . . . . . . . . . . . : {lease.lease_seconds} seconds")
    return CommandResult(output=lines)
