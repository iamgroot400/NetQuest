"""The frame delivery loop.

This is the only place in the simulator that moves a frame from one device to
another. Every command — ping, ARP resolution, an ICMP error — goes through it,
which is why a pulled cable or a wrong netmask genuinely breaks connectivity:
there is no code path that can report a reply without a frame having arrived.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from ..arp.packet import ArpPacket
from ..ethernet.frame import EthernetFrame, EtherType, next_flow_id
from ..icmp.message import IcmpMessage
from ..ipv4.packet import IPv4Packet
from .events import EventType, PacketSnapshot, Severity, SimEvent
from .mac import BROADCAST_MAC
from .models import Emission, Interface
from .network import Network

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..devices.base import Device

#: Ethernet has no TTL, so a physical loop between switches floods forever.
#: The MVP has no spanning tree, so the loop is capped and reported honestly
#: rather than hanging the request.
DEFAULT_HOP_LIMIT = 500


class SimulationEngine:
    def __init__(self, network: Network, hop_limit: int = DEFAULT_HOP_LIMIT) -> None:
        self.network = network
        self.hop_limit = hop_limit
        self.events: list[SimEvent] = []
        self.packets: dict[str, PacketSnapshot] = {}
        self.storm_detected = False
        self._seq = 0
        self._hops = 0

    # -- event recording -------------------------------------------------

    def log(
        self,
        type: EventType,
        message: str,
        *,
        severity: Severity = Severity.INFO,
        device: "Device | None" = None,
        interface: Interface | None = None,
        link_id: str | None = None,
        from_device_id: str | None = None,
        to_device_id: str | None = None,
        frame: EthernetFrame | None = None,
    ) -> SimEvent:
        self._seq += 1
        event = SimEvent(
            seq=self._seq,
            type=type,
            message=message,
            severity=severity,
            device_id=device.id if device else None,
            device_name=device.name if device else None,
            interface_id=interface.id if interface else None,
            interface_name=interface.name if interface else None,
            link_id=link_id,
            from_device_id=from_device_id,
            to_device_id=to_device_id,
            frame_uid=frame.uid if frame else None,
            flow_id=frame.flow_id if frame else None,
        )
        self.events.append(event)
        return event

    def snapshot(self, frame: EthernetFrame) -> PacketSnapshot:
        """Create (or fetch) the inspector record for a frame."""
        existing = self.packets.get(frame.uid)
        if existing:
            return existing

        snap = PacketSnapshot(
            frame_uid=frame.uid,
            flow_id=frame.flow_id,
            summary=frame.summary(),
            ethertype=frame.ethertype.value,
            src_mac=frame.src_mac,
            dst_mac=frame.dst_mac,
        )
        payload = frame.payload
        if isinstance(payload, ArpPacket):
            snap.summary = payload.summary()
            snap.arp_operation = payload.operation.value
            snap.arp_sender_ip = payload.sender_ip
            snap.arp_target_ip = payload.target_ip
            snap.arp_sender_mac = payload.sender_mac
            snap.arp_target_mac = payload.target_mac
        elif isinstance(payload, IPv4Packet):
            snap.protocol = payload.protocol.value
            snap.src_ip = payload.src_ip
            snap.dst_ip = payload.dst_ip
            snap.ttl = payload.ttl
            snap.length = payload.length
            inner = payload.payload
            if isinstance(inner, IcmpMessage):
                snap.summary = inner.summary()
                snap.icmp_type = inner.type.value
                snap.icmp_code = inner.code.value or None
                snap.icmp_sequence = inner.sequence
                snap.icmp_identifier = inner.identifier
            else:
                snap.summary = payload.summary()

        self.packets[frame.uid] = snap
        return snap

    # -- delivery --------------------------------------------------------

    def run(self, source: "Device", emissions: list[Emission]) -> None:
        """Carry frames across the wire until the network goes quiet.

        Re-entrant: a router resolving ARP mid-forward calls back into this
        method. The hop budget and the event list are shared across nesting so
        a storm is still bounded.
        """
        queue: deque[tuple["Device", Emission]] = deque((source, e) for e in emissions)

        while queue:
            if self._hops >= self.hop_limit:
                if not self.storm_detected:
                    self.storm_detected = True
                    self.log(
                        EventType.FRAME_DROPPED,
                        f"Hop limit of {self.hop_limit} reached — traffic stopped. "
                        "A switching loop floods frames forever without spanning tree.",
                        severity=Severity.ERROR,
                    )
                return

            device, emission = queue.popleft()
            frame = emission.frame
            assert isinstance(frame, EthernetFrame)
            out_iface = device.interface(emission.interface_id)

            if out_iface is None:
                continue

            if not out_iface.enabled:
                self.log(
                    EventType.FRAME_DROPPED,
                    f"{device.name}: {out_iface.name} is down — frame dropped",
                    severity=Severity.ERROR,
                    device=device,
                    interface=out_iface,
                    frame=frame,
                )
                continue

            link = self.network.link_for(out_iface.id)
            if link is None:
                self.log(
                    EventType.FRAME_DROPPED,
                    f"{device.name}: no cable attached to {out_iface.name} — frame dropped",
                    severity=Severity.ERROR,
                    device=device,
                    interface=out_iface,
                    frame=frame,
                )
                continue

            if not link.is_up:
                self.log(
                    EventType.FRAME_DROPPED,
                    f"{device.name}: cable on {out_iface.name} is disconnected — frame dropped",
                    severity=Severity.ERROR,
                    device=device,
                    interface=out_iface,
                    link_id=link.id,
                    frame=frame,
                )
                continue

            peer = self.network.peer_of(out_iface.id)
            if peer is None:
                self.log(
                    EventType.FRAME_DROPPED,
                    f"{device.name}: {out_iface.name} leads nowhere — frame dropped",
                    severity=Severity.ERROR,
                    device=device,
                    interface=out_iface,
                    frame=frame,
                )
                continue

            peer_device, peer_iface = peer
            if not peer_iface.enabled:
                self.log(
                    EventType.FRAME_DROPPED,
                    f"{peer_device.name}: {peer_iface.name} is down — frame dropped",
                    severity=Severity.ERROR,
                    device=peer_device,
                    interface=peer_iface,
                    link_id=link.id,
                    frame=frame,
                )
                continue

            self._hops += 1
            snap = self.snapshot(frame)
            if not snap.path:
                snap.path.append(device.name)
            if snap.path[-1] != peer_device.name:
                snap.path.append(peer_device.name)

            self.log(
                EventType.FRAME_TRANSMITTED,
                f"{device.name} {out_iface.name} → {peer_device.name} {peer_iface.name}: "
                f"{snap.summary}",
                device=device,
                interface=out_iface,
                link_id=link.id,
                from_device_id=device.id,
                to_device_id=peer_device.id,
                frame=frame,
            )

            for result in peer_device.receive_frame(frame, peer_iface, self):
                queue.append((peer_device, result))

    def send(self, device: "Device", interface_id: str, frame: EthernetFrame) -> None:
        """Originate a frame from a device."""
        self.run(device, [Emission(interface_id=interface_id, frame=frame)])

    # -- ARP -------------------------------------------------------------

    def resolve_arp(
        self, device: "Device", ip: str, interface: Interface
    ) -> str | None:
        """Find the MAC for `ip`, consulting the cache then asking the wire.

        Returns None when nobody answered, which is exactly how a real host
        fails: the packet it was holding is discarded.
        """
        cached = device.arp_table.lookup(ip)
        if cached:
            self.log(
                EventType.ARP_CACHE_HIT,
                f"{device.name}: ARP cache hit — {ip} is at {cached}",
                device=device,
                interface=interface,
            )
            return cached

        if not interface.has_ip:
            self.log(
                EventType.ARP_FAILED,
                f"{device.name}: cannot ARP for {ip} — {interface.name} has no IP address",
                severity=Severity.ERROR,
                device=device,
                interface=interface,
            )
            return None

        request = ArpPacket.request(interface.mac, interface.ipv4 or "", ip)
        frame = EthernetFrame(
            src_mac=interface.mac,
            dst_mac=BROADCAST_MAC,
            ethertype=EtherType.ARP,
            payload=request,
            flow_id=next_flow_id(),
        )
        self.log(
            EventType.ARP_REQUEST,
            f"{device.name}: {request.summary()}",
            device=device,
            interface=interface,
            frame=frame,
        )
        self.send(device, interface.id, frame)

        resolved = device.arp_table.lookup(ip)
        if resolved:
            self.log(
                EventType.ARP_RESOLVED,
                f"{device.name}: ARP resolved {ip} → {resolved}",
                severity=Severity.SUCCESS,
                device=device,
                interface=interface,
            )
        else:
            self.log(
                EventType.ARP_FAILED,
                f"{device.name}: no ARP reply for {ip} — nothing on this network answered",
                severity=Severity.ERROR,
                device=device,
                interface=interface,
            )
        return resolved
