"""Layer 3 router.

Forwards IPv4 between its connected subnets: decrement TTL, longest-prefix
match, resolve the next hop's MAC, re-encapsulate in a brand new frame. When it
cannot forward, it says why with a real ICMP error rather than silence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..arp.packet import ArpOperation, ArpPacket
from ..core.addressing import is_broadcast_ip
from ..core.events import EventType, Severity
from ..core.models import DeviceConfig, Emission, Interface
from ..ethernet.frame import EtherType, EthernetFrame, next_flow_id
from ..icmp.message import IcmpCode, IcmpMessage, IcmpType
from ..ipv4.packet import IPProtocol, IPv4Packet
from ..routing.table import RoutingTable
from .base import Device

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine


class Router(Device):
    kind = "router"

    def __init__(
        self,
        id: str,
        name: str,
        interfaces: list[Interface],
        config: DeviceConfig | None = None,
    ) -> None:
        super().__init__(id, name, interfaces, config)
        #: Populated by the loader from connected subnets + static routes.
        self.routing_table = RoutingTable()
        self.icmp_inbox: list[tuple[IPv4Packet, IcmpMessage]] = []

    # -- reception --------------------------------------------------------

    def receive_frame(
        self,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        if not frame.addressed_to(in_interface.mac):
            engine.log(
                EventType.FRAME_DROPPED,
                f"{self.name}: frame for {frame.dst_mac} is not for {in_interface.name} — discarded",
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        if frame.ethertype is EtherType.ARP:
            return self._handle_arp(frame, in_interface, engine)
        if frame.ethertype is EtherType.IPV4:
            return self._handle_ipv4(frame, in_interface, engine)
        return []

    def _handle_arp(
        self,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        arp = frame.payload
        assert isinstance(arp, ArpPacket)

        if arp.operation is ArpOperation.REQUEST:
            if in_interface.ipv4 != arp.target_ip:
                engine.log(
                    EventType.FRAME_DROPPED,
                    f"{self.name}: ARP request is for {arp.target_ip}, "
                    f"not {in_interface.name} — ignored",
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )
                return []

            self.arp_table.insert(arp.sender_ip, arp.sender_mac)
            reply = arp.reply(in_interface.mac)
            reply_frame = EthernetFrame(
                src_mac=in_interface.mac,
                dst_mac=arp.sender_mac,
                ethertype=EtherType.ARP,
                payload=reply,
                flow_id=frame.flow_id,
            )
            engine.log(
                EventType.ARP_REPLY,
                f"{self.name}: {reply.summary()}",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=reply_frame,
            )
            return [Emission(interface_id=in_interface.id, frame=reply_frame)]

        if arp.target_mac == in_interface.mac or arp.target_ip == in_interface.ipv4:
            self.arp_table.insert(arp.sender_ip, arp.sender_mac)
            engine.log(
                EventType.ARP_REPLY,
                f"{self.name}: cached {arp.sender_ip} → {arp.sender_mac}",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=frame,
            )
        return []

    def _handle_ipv4(
        self,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        packet = frame.payload
        assert isinstance(packet, IPv4Packet)

        if self.owns_ip(packet.dst_ip) or is_broadcast_ip(
            packet.dst_ip, in_interface.ipv4, in_interface.netmask
        ):
            return self._deliver_locally(packet, frame, in_interface, engine)

        return self._forward(packet, frame, in_interface, engine)

    def _deliver_locally(
        self,
        packet: IPv4Packet,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        if packet.protocol is not IPProtocol.ICMP:
            return []
        icmp = packet.payload
        assert isinstance(icmp, IcmpMessage)

        if icmp.type is IcmpType.ECHO_REQUEST:
            engine.log(
                EventType.ICMP_REQUEST,
                f"{self.name}: echo request for its own address {packet.dst_ip} — replying",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            reply = IPv4Packet(
                src_ip=packet.dst_ip,
                dst_ip=packet.src_ip,
                protocol=IPProtocol.ICMP,
                payload=icmp.echo_reply(),
                length=packet.length,
            )
            return self.originate(reply, engine, flow_id=frame.flow_id)

        self.icmp_inbox.append((packet, icmp))
        engine.log(
            EventType.PACKET_DELIVERED,
            f"{self.name}: received {icmp.summary()} from {packet.src_ip}",
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return []

    # -- forwarding -------------------------------------------------------

    def _forward(
        self,
        packet: IPv4Packet,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        forwarded = packet.decremented()
        engine.log(
            EventType.TTL_DECREMENT,
            f"{self.name}: TTL {packet.ttl} → {forwarded.ttl} for {packet.dst_ip}",
            device=self,
            interface=in_interface,
            frame=frame,
        )

        if forwarded.ttl <= 0:
            engine.log(
                EventType.TTL_EXPIRED,
                f"{self.name}: TTL expired in transit — packet to {packet.dst_ip} discarded",
                severity=Severity.ERROR,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return self._icmp_error(
                packet, in_interface, engine, IcmpType.TIME_EXCEEDED, IcmpCode.TTL_EXCEEDED_IN_TRANSIT
            )

        route = self.routing_table.lookup(packet.dst_ip)
        if route is None:
            engine.log(
                EventType.ROUTE_MISS,
                f"{self.name}: no route to {packet.dst_ip} — packet dropped",
                severity=Severity.ERROR,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return self._icmp_error(
                packet, in_interface, engine, IcmpType.DESTINATION_UNREACHABLE, IcmpCode.NET_UNREACHABLE
            )

        out_iface = self.interface(route.interface_id)
        if out_iface is None or not out_iface.enabled:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: outgoing interface for {packet.dst_ip} is down — packet dropped",
                severity=Severity.ERROR,
                device=self,
                frame=frame,
            )
            return self._icmp_error(
                packet, in_interface, engine, IcmpType.DESTINATION_UNREACHABLE, IcmpCode.HOST_UNREACHABLE
            )

        next_hop = route.gateway or packet.dst_ip
        engine.log(
            EventType.ROUTE_LOOKUP,
            f"{self.name}: {packet.dst_ip} matches {route.destination}/{route.prefix_length} "
            f"({route.kind.value}) via {out_iface.name}"
            + ("" if route.gateway is None else f", next hop {route.gateway}"),
            device=self,
            interface=out_iface,
            frame=frame,
        )

        dst_mac = engine.resolve_arp(self, next_hop, out_iface)
        if dst_mac is None:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: could not resolve {next_hop} — packet to {packet.dst_ip} dropped",
                severity=Severity.ERROR,
                device=self,
                interface=out_iface,
                frame=frame,
            )
            return self._icmp_error(
                packet, in_interface, engine, IcmpType.DESTINATION_UNREACHABLE, IcmpCode.HOST_UNREACHABLE
            )

        # A router builds a completely new frame; only the flow id carries over
        # so the inspector can still draw one end-to-end path.
        out_frame = EthernetFrame(
            src_mac=out_iface.mac,
            dst_mac=dst_mac,
            ethertype=EtherType.IPV4,
            payload=forwarded,
            flow_id=frame.flow_id,
        )
        return [Emission(interface_id=out_iface.id, frame=out_frame)]

    def select_source_ip(self, dst_ip: str) -> str | None:
        """The address a packet to `dst_ip` would leave with, if it can leave."""
        route = self.routing_table.lookup(dst_ip)
        if route is None:
            return None
        iface = self.interface(route.interface_id)
        return iface.ipv4 if iface and iface.has_ip else None

    def send_ipv4(
        self,
        packet: IPv4Packet,
        engine: "SimulationEngine",
        flow_id: str | None = None,
    ) -> list[Emission]:
        """Alias of `originate`, so ping works identically on hosts and routers."""
        return self.originate(packet, engine, flow_id)

    def originate(
        self,
        packet: IPv4Packet,
        engine: "SimulationEngine",
        flow_id: str | None = None,
    ) -> list[Emission]:
        """Send a packet the router itself created (a reply or an ICMP error)."""
        route = self.routing_table.lookup(packet.dst_ip)
        if route is None:
            engine.log(
                EventType.ROUTE_MISS,
                f"{self.name}: no route back to {packet.dst_ip} — packet dropped",
                severity=Severity.ERROR,
                device=self,
            )
            return []

        out_iface = self.interface(route.interface_id)
        if out_iface is None or not out_iface.enabled:
            return []

        # Source from the interface the packet actually leaves by, unless the
        # caller already pinned a source (an echo reply keeps the pinged address).
        if not self.owns_ip(packet.src_ip) and out_iface.has_ip:
            packet = IPv4Packet(
                src_ip=out_iface.ipv4 or packet.src_ip,
                dst_ip=packet.dst_ip,
                protocol=packet.protocol,
                payload=packet.payload,
                ttl=packet.ttl,
                length=packet.length,
            )

        next_hop = route.gateway or packet.dst_ip
        dst_mac = engine.resolve_arp(self, next_hop, out_iface)
        if dst_mac is None:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: could not resolve {next_hop} — packet to {packet.dst_ip} dropped",
                severity=Severity.ERROR,
                device=self,
                interface=out_iface,
            )
            return []

        out_frame = EthernetFrame(
            src_mac=out_iface.mac,
            dst_mac=dst_mac,
            ethertype=EtherType.IPV4,
            payload=packet,
            flow_id=flow_id or next_flow_id(),
        )
        engine.log(
            EventType.FRAME_SENT,
            f"{self.name}: sending {packet.protocol.value} to {packet.dst_ip}",
            device=self,
            interface=out_iface,
            frame=out_frame,
        )
        return [Emission(interface_id=out_iface.id, frame=out_frame)]

    def _icmp_error(
        self,
        original: IPv4Packet,
        in_interface: Interface,
        engine: "SimulationEngine",
        type: IcmpType,
        code: IcmpCode,
    ) -> list[Emission]:
        """Report a forwarding failure back to the sender.

        Errors are never generated in response to errors — otherwise a routing
        loop turns into an endless exchange of unreachable messages.
        """
        inner = original.payload
        if isinstance(inner, IcmpMessage) and inner.is_error:
            return []
        if not in_interface.has_ip:
            return []

        error_packet = IPv4Packet(
            src_ip=in_interface.ipv4 or "",
            dst_ip=original.src_ip,
            protocol=IPProtocol.ICMP,
            payload=IcmpMessage(type=type, code=code),
        )
        engine.log(
            EventType.ICMP_ERROR,
            f"{self.name}: sending ICMP {type.value} ({code.value}) to {original.src_ip}",
            severity=Severity.WARNING,
            device=self,
            interface=in_interface,
        )
        return self.originate(error_packet, engine)

    # -- runtime state ----------------------------------------------------

    def state(self) -> dict[str, Any]:
        return {
            "arp_table": self.arp_table.to_dict(),
            "mac_table": {},
            "routing_table": [
                {
                    "destination": r.destination,
                    "netmask": r.netmask,
                    "gateway": r.gateway,
                    "interface_id": r.interface_id,
                    "kind": r.kind.value,
                    "prefix_length": r.prefix_length,
                }
                for r in self.routing_table.sorted_routes()
            ],
        }
