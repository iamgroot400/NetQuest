"""Wire format for the topology document.

The frontend owns this document and sends it with every request. It is also
exactly what `Save Network` writes to disk, minus the `runtime` block.
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


class DeviceConfigSchema(BaseModel):
    gateway: str | None = None
    static_routes: list[StaticRouteSchema] = Field(default_factory=list)


class DeviceRuntimeSchema(BaseModel):
    """Learned tables. Round-tripped between requests, stripped on export."""

    arp_table: dict[str, str] = Field(default_factory=dict)
    mac_table: dict[str, str] = Field(default_factory=dict)


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
