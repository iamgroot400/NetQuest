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
class DeviceConfig:
    gateway: str | None = None
    static_routes: list[StaticRouteConfig] = field(default_factory=list)


@dataclass
class Emission:
    """A frame a device wants to put on the wire out of one of its interfaces."""

    interface_id: str
    frame: object
