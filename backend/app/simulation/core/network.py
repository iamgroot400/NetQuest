"""The topology graph the engine walks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Interface, Link

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..devices.base import Device


class Network:
    """Devices plus the cables between them.

    Built once per command from the topology document the frontend sends. The
    index from interface id to link is what makes hop-by-hop delivery cheap.
    """

    def __init__(self, devices: list["Device"], links: list[Link]) -> None:
        self.devices: dict[str, "Device"] = {d.id: d for d in devices}
        self.links: dict[str, Link] = {link.id: link for link in links}
        self._link_by_interface: dict[str, Link] = {}
        for link in links:
            self._link_by_interface[link.a.interface_id] = link
            self._link_by_interface[link.b.interface_id] = link

    # -- lookups ---------------------------------------------------------

    def device(self, device_id: str) -> "Device | None":
        return self.devices.get(device_id)

    def device_by_name(self, name: str) -> "Device | None":
        lowered = name.lower()
        for dev in self.devices.values():
            if dev.name.lower() == lowered:
                return dev
        return None

    def link_for(self, interface_id: str) -> Link | None:
        return self._link_by_interface.get(interface_id)

    def peer_of(self, interface_id: str) -> tuple["Device", Interface] | None:
        """Follow the cable attached to an interface to the far end."""
        link = self._link_by_interface.get(interface_id)
        if link is None:
            return None
        far = link.other_end(interface_id)
        if far is None:
            return None
        device = self.devices.get(far.device_id)
        if device is None:
            return None
        interface = device.interface(far.interface_id)
        if interface is None:
            return None
        return device, interface

    def devices_with_ip(self, ip: str) -> list["Device"]:
        """Every device holding this address — used to flag duplicate IPs."""
        return [d for d in self.devices.values() if d.owns_ip(ip)]

    def all_interfaces(self) -> list[Interface]:
        return [iface for dev in self.devices.values() for iface in dev.interfaces]
