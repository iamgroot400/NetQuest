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
    path: list[str] = Field(default_factory=list)


class RouteSchema(BaseModel):
    destination: str
    netmask: str
    gateway: str | None = None
    interface_id: str
    kind: str
    prefix_length: int


class DeviceStateSchema(BaseModel):
    arp_table: dict[str, str] = Field(default_factory=dict)
    mac_table: dict[str, str] = Field(default_factory=dict)
    routing_table: list[RouteSchema] = Field(default_factory=list)


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


class ValidationIssue(BaseModel):
    severity: str  # "error" | "warning"
    device_id: str | None = None
    device_name: str | None = None
    interface_id: str | None = None
    message: str


class ValidationResponse(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
