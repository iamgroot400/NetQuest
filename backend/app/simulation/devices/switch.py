"""Layer 2 switch.

Implements the three rules that define a switch: learn the source address of
every frame, forward known unicast out a single port, and flood everything
else. There is no spanning tree, so a physical loop really does storm — the
engine's hop limit stops it and says so.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.events import EventType, Severity
from ..core.models import DeviceConfig, Emission, Interface
from .base import Device

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine
    from ..ethernet.frame import EthernetFrame


class Switch(Device):
    kind = "switch"

    def __init__(
        self,
        id: str,
        name: str,
        interfaces: list[Interface],
        config: DeviceConfig | None = None,
    ) -> None:
        super().__init__(id, name, interfaces, config)
        #: MAC address -> interface id it was last seen on.
        self.mac_table: dict[str, str] = {}

    def receive_frame(
        self,
        frame: "EthernetFrame",
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        self._learn(frame.src_mac, in_interface, engine)

        if frame.is_broadcast:
            return self._flood(
                frame,
                in_interface,
                engine,
                f"{self.name}: broadcast frame — flooding out every other port",
            )

        out_id = self.mac_table.get(frame.dst_mac)

        if out_id is None:
            return self._flood(
                frame,
                in_interface,
                engine,
                f"{self.name}: {frame.dst_mac} is not in the MAC address table — "
                "flooding out every other port",
            )

        if out_id == in_interface.id:
            engine.log(
                EventType.FRAME_DROPPED,
                f"{self.name}: {frame.dst_mac} lives on {in_interface.name}, "
                "the port the frame came from — dropped",
                severity=Severity.WARNING,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        out_iface = self.interface(out_id)
        if out_iface is None or not out_iface.enabled:
            engine.log(
                EventType.FRAME_DROPPED,
                f"{self.name}: port for {frame.dst_mac} is unavailable — frame dropped",
                severity=Severity.ERROR,
                device=self,
                frame=frame,
            )
            return []

        engine.log(
            EventType.FRAME_RECEIVED,
            f"{self.name}: {frame.dst_mac} is on {out_iface.name} — forwarding",
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return [Emission(interface_id=out_id, frame=frame)]

    def _learn(
        self, mac: str, in_interface: Interface, engine: "SimulationEngine"
    ) -> None:
        if self.mac_table.get(mac) == in_interface.id:
            return
        self.mac_table[mac] = in_interface.id
        engine.log(
            EventType.MAC_LEARNED,
            f"{self.name}: learned {mac} on {in_interface.name}",
            severity=Severity.SUCCESS,
            device=self,
            interface=in_interface,
        )

    def _flood(
        self,
        frame: "EthernetFrame",
        in_interface: Interface,
        engine: "SimulationEngine",
        message: str,
    ) -> list[Emission]:
        # A port with no live cable is physically down, so real hardware does
        # not flood out of it either. Filtering here also keeps the event log
        # free of a "dropped" line for every empty port on the switch.
        targets = [
            i
            for i in self.enabled_interfaces
            if i.id != in_interface.id and self._port_is_live(i, engine)
        ]
        if not targets:
            engine.log(
                EventType.FRAME_DROPPED,
                f"{self.name}: nowhere to flood to — frame dropped",
                severity=Severity.WARNING,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        engine.log(
            EventType.FRAME_FLOODED,
            message,
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return [Emission(interface_id=i.id, frame=frame) for i in targets]

    @staticmethod
    def _port_is_live(interface: Interface, engine: "SimulationEngine") -> bool:
        link = engine.network.link_for(interface.id)
        return link is not None and link.is_up

    # -- runtime state ----------------------------------------------------

    def state(self) -> dict[str, Any]:
        return {"arp_table": {}, "mac_table": dict(self.mac_table)}

    def load_state(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        table = state.get("mac_table") or {}
        # Drop entries pointing at ports that no longer exist.
        valid = {i.id for i in self.interfaces}
        self.mac_table = {m: p for m, p in table.items() if p in valid}
