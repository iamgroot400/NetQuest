"""Request and response models for the simulation API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .topology import TopologySchema


class CommandRequest(BaseModel):
    topology: TopologySchema
    device_id: str
    command: str


class SimEventSchema(BaseModel):
    seq: int
    type: str
    message: str
    severity: str = "info"
    device_id: str | None = None
    device_name: str | None = None
    interface_id: str | None = None
    interface_name: str | None = None
    link_id: str | None = None
    from_device_id: str | None = None
    to_device_id: str | None = None
    frame_uid: str | None = None
    flow_id: str | None = None


class PacketSchema(BaseModel):
    frame_uid: str
    flow_id: str
    summary: str
    ethertype: str
    src_mac: str
    dst_mac: str
    protocol: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    ttl: int | None = None
    length: int | None = None
    icmp_type: str | None = None
    icmp_code: str | None = None
    icmp_sequence: int | None = None
    icmp_identifier: int | None = None
    arp_operation: str | None = None
    arp_sender_ip: str | None = None
    arp_target_ip: str | None = None
    arp_sender_mac: str | None = None
    arp_target_mac: str | None = None
    transport_protocol: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    tcp_flag: str | None = None
    dns_query_name: str | None = None
    dns_query_type: str | None = None
    dns_status: str | None = None
    dns_answers: list[str] = Field(default_factory=list)
    dhcp_type: str | None = None
    dhcp_offered_ip: str | None = None
    encapsulated: bool = False
    inner_summary: str | None = None
    path: list[str] = Field(default_factory=list)


class RouteSchema(BaseModel):
    destination: str
    netmask: str
    gateway: str | None = None
    interface_id: str
    kind: str
    prefix_length: int


class AssignedConfigSchema(BaseModel):
    """What DHCP configured on a client.

    The frontend writes this back into the topology document, so a lease
    genuinely reconfigures the device rather than being a one-off readout.
    """

    interface_id: str | None = None
    ipv4: str | None = None
    netmask: str | None = None
    gateway: str | None = None
    dns_server: str | None = None
    lease_seconds: int | None = None
    server_ip: str | None = None


class NatTranslationSchema(BaseModel):
    inside_ip: str
    inside_port: int | None = None
    outside_ip: str
    outside_port: int | None = None
    protocol: str
    destination_ip: str


class DeviceStateSchema(BaseModel):
    arp_table: dict[str, str] = Field(default_factory=dict)
    mac_table: dict[str, str] = Field(default_factory=dict)
    routing_table: list[RouteSchema] = Field(default_factory=list)
    dns_cache: dict[str, str] = Field(default_factory=dict)
    dhcp_leases: dict[str, str] = Field(default_factory=dict)
    firewall_hits: dict[str, int] = Field(default_factory=dict)
    nat_translations: list[NatTranslationSchema] = Field(default_factory=list)
    #: Present only when DHCP handed this device a lease during the command.
    assigned: AssignedConfigSchema | None = None


class CommandResponse(BaseModel):
    #: Lines the terminal prints, verbatim.
    output: list[str] = Field(default_factory=list)
    #: Ordered trace: drives the animation and the event log.
    events: list[SimEventSchema] = Field(default_factory=list)
    #: One record per frame that crossed a wire, for the packet inspector.
    packets: list[PacketSchema] = Field(default_factory=list)
    #: Learned tables to write back into the topology document.
    device_state: dict[str, DeviceStateSchema] = Field(default_factory=dict)
    success: bool = True


class ConnectionRequest(BaseModel):
    topology: TopologySchema
    source_device_id: str
    #: An address or a hostname — a name is resolved through the simulated DNS.
    destination: str
    port: int = 80
    protocol: str = "TCP"  # "TCP" | "UDP"


class ConnectionResponse(BaseModel):
    reachable: bool
    #: open | refused | filtered | unreachable | no-route | dns-failure
    outcome: str
    detail: str
    target: str
    resolved_ip: str | None = None
    port: int | None = None
    protocol: str = "TCP"
    #: Devices the outbound traffic actually crossed, in order.
    path: list[str] = Field(default_factory=list)
    blocked_at: str | None = None
    blocked_reason: str | None = None
    dns_detail: str | None = None
    events: list[SimEventSchema] = Field(default_factory=list)
    packets: list[PacketSchema] = Field(default_factory=list)
    device_state: dict[str, DeviceStateSchema] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    severity: str  # "error" | "warning"
    device_id: str | None = None
    device_name: str | None = None
    interface_id: str | None = None
    message: str


class ValidationResponse(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
