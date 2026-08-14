"""Shared value objects used across the engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from .addressing import is_valid_ipv4, is_valid_netmask


@dataclass
class Interface:
    id: str
    name: str
    mac: str
    device_id: str = ""
    ipv4: str | None = None
    netmask: str | None = None
    enabled: bool = True

    @property
    def has_ip(self) -> bool:
        return is_valid_ipv4(self.ipv4) and is_valid_netmask(self.netmask)

    @property
    def status(self) -> str:
        return "up" if self.enabled else "administratively down"


@dataclass
class LinkEnd:
    device_id: str
    interface_id: str


@dataclass
class Link:
    id: str
    a: LinkEnd
    b: LinkEnd
    # A "down" link models an unplugged or cut cable: it stays visible on the
    # canvas but carries nothing, which is what troubleshooting missions need.
    status: str = "up"

    @property
    def is_up(self) -> bool:
        return self.status == "up"

    def other_end(self, interface_id: str) -> LinkEnd | None:
        if self.a.interface_id == interface_id:
            return self.b
        if self.b.interface_id == interface_id:
            return self.a
        return None


@dataclass
class StaticRouteConfig:
    destination: str
    netmask: str
    gateway: str


@dataclass
class ServiceConfig:
    """A port a device listens on. Disable it and the port closes for real."""

    name: str
    protocol: str  # "TCP" | "UDP"
    port: int
    enabled: bool = True


@dataclass
class DnsRecordConfig:
    name: str
    type: str  # "A" | "CNAME" | "MX"
    value: str
    priority: int = 10


@dataclass
class DhcpPoolConfig:
    start: str
    end: str
    netmask: str
    gateway: str | None = None
    dns: str | None = None
    lease_seconds: int = 86400
    enabled: bool = True


@dataclass
class FirewallRuleConfig:
    action: str  # "allow" | "deny"
    protocol: str = "any"  # "any" | "tcp" | "udp" | "icmp"
    port: int | None = None
    source: str = "any"  # CIDR or "any"
    destination: str = "any"
    description: str = ""


@dataclass
class NatConfig:
    enabled: bool = False
    #: Traffic leaving this interface is translated to its address.
    outside_interface_id: str | None = None


@dataclass
class VpnConfig:
    #: On a client: the gateway to tunnel to, and what lies behind it.
    server: str | None = None
    remote_network: str | None = None
    remote_netmask: str | None = None
    #: The address the client uses inside the tunnel.
    tunnel_ip: str | None = None
    #: On a gateway: accept tunnels and forward what comes out of them.
    is_gateway: bool = False
    enabled: bool = True


@dataclass
class DeviceConfig:
    gateway: str | None = None
    #: Where this device sends DNS queries.
    dns_server: str | None = None
    #: When true the device asks DHCP for its address instead of being static.
    dhcp_client: bool = False
    static_routes: list[StaticRouteConfig] = field(default_factory=list)
    services: list[ServiceConfig] = field(default_factory=list)
    dns_records: list[DnsRecordConfig] = field(default_factory=list)
    dhcp_pool: DhcpPoolConfig | None = None
    firewall_rules: list[FirewallRuleConfig] = field(default_factory=list)
    firewall_default_policy: str = "allow"
    nat: NatConfig | None = None
    vpn: VpnConfig | None = None


@dataclass
class Emission:
    """A frame a device wants to put on the wire out of one of its interfaces."""

    interface_id: str
    frame: object
