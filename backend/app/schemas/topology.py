"""Wire format for the topology document.

The frontend owns this document and sends it with every request. It is also
exactly what `Save Network` writes to disk, minus the `runtime` block.

Every field here is configuration the simulation actually reads. Adding a
service, a DNS record or a firewall rule changes what the network does.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

TOPOLOGY_VERSION = 1


class DeviceType(str, Enum):
    PC = "pc"
    SWITCH = "switch"
    ROUTER = "router"
    SERVER = "server"
    FIREWALL = "firewall"


class Position(BaseModel):
    x: float = 0
    y: float = 0


class InterfaceSchema(BaseModel):
    id: str
    name: str
    mac: str
    ipv4: str | None = None
    netmask: str | None = None
    enabled: bool = True


class StaticRouteSchema(BaseModel):
    destination: str
    netmask: str
    gateway: str


class ServiceSchema(BaseModel):
    """A listening port. Disable it and the port genuinely closes."""

    name: str
    protocol: str = "TCP"  # "TCP" | "UDP"
    port: int
    enabled: bool = True


class DnsRecordSchema(BaseModel):
    name: str
    type: str = "A"  # "A" | "CNAME" | "MX"
    value: str
    priority: int = 10


class DhcpPoolSchema(BaseModel):
    start: str
    end: str
    netmask: str
    gateway: str | None = None
    dns: str | None = None
    lease_seconds: int = 86400
    enabled: bool = True


class FirewallRuleSchema(BaseModel):
    action: str = "allow"  # "allow" | "deny"
    protocol: str = "any"  # "any" | "tcp" | "udp" | "icmp"
    port: int | None = None
    source: str = "any"  # CIDR, a bare address, or "any"
    destination: str = "any"
    description: str = ""


class NatSchema(BaseModel):
    enabled: bool = False
    #: Traffic leaving here is translated to this interface's address.
    outside_interface_id: str | None = None


class VpnSchema(BaseModel):
    #: Client side: tunnel to this gateway to reach this network.
    server: str | None = None
    remote_network: str | None = None
    remote_netmask: str | None = None
    #: The address the client takes *inside* the tunnel. Set it to one on the
    #: remote network and the gateway will answer ARP for it, which is what
    #: makes replies come back through the tunnel instead of around it.
    tunnel_ip: str | None = None
    #: Gateway side: accept tunnels and forward what comes out of them.
    is_gateway: bool = False
    enabled: bool = True


class DeviceConfigSchema(BaseModel):
    gateway: str | None = None
    dns_server: str | None = None
    #: Ask DHCP for an address instead of being configured statically.
    dhcp_client: bool = False
    static_routes: list[StaticRouteSchema] = Field(default_factory=list)
    services: list[ServiceSchema] = Field(default_factory=list)
    dns_records: list[DnsRecordSchema] = Field(default_factory=list)
    dhcp_pool: DhcpPoolSchema | None = None
    firewall_rules: list[FirewallRuleSchema] = Field(default_factory=list)
    firewall_default_policy: str = "allow"
    nat: NatSchema | None = None
    vpn: VpnSchema | None = None


class DeviceRuntimeSchema(BaseModel):
    """Learned tables. Round-tripped between requests, stripped on export."""

    arp_table: dict[str, str] = Field(default_factory=dict)
    mac_table: dict[str, str] = Field(default_factory=dict)
    dns_cache: dict[str, str] = Field(default_factory=dict)
    #: Server side: client MAC -> leased address.
    dhcp_leases: dict[str, str] = Field(default_factory=dict)
    #: Firewall rule index -> packets it decided.
    firewall_hits: dict[str, int] = Field(default_factory=dict)


class DeviceSchema(BaseModel):
    id: str
    type: DeviceType
    name: str
    position: Position = Field(default_factory=Position)
    interfaces: list[InterfaceSchema] = Field(default_factory=list)
    config: DeviceConfigSchema = Field(default_factory=DeviceConfigSchema)
    runtime: DeviceRuntimeSchema = Field(default_factory=DeviceRuntimeSchema)


class LinkEndSchema(BaseModel):
    device_id: str
    interface_id: str


class LinkSchema(BaseModel):
    id: str
    a: LinkEndSchema
    b: LinkEndSchema
    status: str = "up"


class TopologySchema(BaseModel):
    version: int = TOPOLOGY_VERSION
    name: str = "Untitled network"
    devices: list[DeviceSchema] = Field(default_factory=list)
    links: list[LinkSchema] = Field(default_factory=list)
