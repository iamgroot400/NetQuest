"""Base class every simulated device derives from.

Adding a new device type means subclassing `Device`, implementing
`receive_frame`, and registering it in `app/simulation/loader.py` plus a
command set in `app/simulation/commands/`. See docs/ADDING-DEVICES.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..arp.table import ArpTable
from ..core.models import DeviceConfig, Emission, Interface

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine
    from ..ethernet.frame import EthernetFrame


class Device(ABC):
    #: Matches the `type` field in the topology document.
    kind: str = "device"

    def __init__(
        self,
        id: str,
        name: str,
        interfaces: list[Interface],
        config: DeviceConfig | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.interfaces = interfaces
        self.config = config or DeviceConfig()
        # Layer 2 devices never populate this; it lives here so the engine can
        # resolve ARP for any device without a type check.
        self.arp_table = ArpTable()

    # -- interface lookups ----------------------------------------------

    def interface(self, interface_id: str) -> Interface | None:
        for iface in self.interfaces:
            if iface.id == interface_id:
                return iface
        return None

    def interface_by_name(self, name: str) -> Interface | None:
        lowered = name.lower()
        for iface in self.interfaces:
            if iface.name.lower() == lowered:
                return iface
        return None

    @property
    def enabled_interfaces(self) -> list[Interface]:
        return [i for i in self.interfaces if i.enabled]

    @property
    def ip_interfaces(self) -> list[Interface]:
        return [i for i in self.enabled_interfaces if i.has_ip]

    def owns_ip(self, ip: str) -> bool:
        return any(i.ipv4 == ip for i in self.interfaces if i.has_ip)

    def owns_mac(self, mac: str) -> bool:
        return any(i.mac == mac for i in self.interfaces)

    # -- behaviour --------------------------------------------------------

    @abstractmethod
    def receive_frame(
        self,
        frame: "EthernetFrame",
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        """Handle a frame that arrived on `in_interface`.

        Return the frames this device wants to send as a result; the engine
        puts them on the wire. Return an empty list to consume or drop.
        """

    # -- runtime state round-trip ----------------------------------------

    def state(self) -> dict[str, Any]:
        """Runtime tables handed back to the frontend after a command."""
        return {"arp_table": self.arp_table.to_dict(), "mac_table": {}}

    def load_state(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        self.arp_table = ArpTable.from_dict(state.get("arp_table"))
