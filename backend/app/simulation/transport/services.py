"""The service catalogue.

A device only answers on a port it is actually listening on, so this table is
what makes "the port is closed" and "the port is filtered" different outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .segment import TransportProtocol


@dataclass(frozen=True)
class WellKnownService:
    name: str
    protocol: TransportProtocol
    port: int
    description: str


TCP = TransportProtocol.TCP
UDP = TransportProtocol.UDP

#: Offered in the UI as one-click services to enable on a server.
WELL_KNOWN: tuple[WellKnownService, ...] = (
    WellKnownService("HTTP", TCP, 80, "Unencrypted web traffic"),
    WellKnownService("HTTPS", TCP, 443, "Encrypted web traffic"),
    WellKnownService("DNS", UDP, 53, "Resolves names to addresses"),
    WellKnownService("DHCP", UDP, 67, "Hands out addresses to clients"),
    WellKnownService("SSH", TCP, 22, "Remote shell"),
    WellKnownService("FTP", TCP, 21, "File transfer"),
    WellKnownService("SMTP", TCP, 25, "Mail delivery"),
    WellKnownService("VPN", UDP, 1194, "Tunnel endpoint"),
)

BY_NAME = {service.name.upper(): service for service in WELL_KNOWN}

#: Reverse lookup used to label ports in command output and the inspector.
_PORT_NAMES = {(s.protocol, s.port): s.name for s in WELL_KNOWN}

#: Ports a DHCP exchange uses. The client has no address yet, so the server
#: replies to the broadcast address on the client port.
DHCP_SERVER_PORT = 67
DHCP_CLIENT_PORT = 68
DNS_PORT = 53
VPN_PORT = 1194


def service_name(protocol: TransportProtocol, port: int) -> str | None:
    return _PORT_NAMES.get((protocol, port))


def describe_port(protocol: TransportProtocol, port: int) -> str:
    """e.g. "80/tcp (HTTP)" — used wherever a port is printed."""
    name = service_name(protocol, port)
    suffix = f" ({name})" if name else ""
    return f"{port}/{protocol.value.lower()}{suffix}"


def lookup(name: str) -> WellKnownService | None:
    return BY_NAME.get(name.strip().upper())


def default_port_for(name: str) -> int | None:
    service = lookup(name)
    return service.port if service else None
