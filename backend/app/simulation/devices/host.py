"""Shared behaviour for end hosts (PCs and servers).

A host has no routing table. It uses the classic end-station decision every
networking course teaches: if the destination is inside my own subnet, send it
straight there; otherwise hand it to my default gateway. Getting either the
netmask or the gateway wrong therefore breaks connectivity for real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..arp.packet import ArpOperation, ArpPacket
from ..core.addressing import is_valid_ipv4, is_broadcast_ip, same_subnet
from ..core.events import EventType, Severity
from ..core.mac import BROADCAST_MAC
from ..core.models import DeviceConfig, Emission, Interface
from ..ethernet.frame import EtherType, EthernetFrame, next_flow_id
from ..icmp.message import IcmpMessage, IcmpType
from ..ipv4.packet import IPProtocol, IPv4Packet
from .base import Device

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine


class Host(Device):
    kind = "host"

    def __init__(
        self,
        id: str,
        name: str,
        interfaces: list[Interface],
        config: DeviceConfig | None = None,
    ) -> None:
        super().__init__(id, name, interfaces, config)
        #: ICMP messages addressed to us, drained by the ping command.
        self.icmp_inbox: list[tuple[IPv4Packet, IcmpMessage]] = []

    @property
    def primary_interface(self) -> Interface | None:
        return self.interfaces[0] if self.interfaces else None

    # -- forwarding decision ---------------------------------------------

    def next_hop_for(self, dst_ip: str) -> tuple[str, Interface] | None:
        """Resolve (next hop IP, outgoing interface), or None if unreachable.

        None means the host has nowhere to send the packet: either it has no
        usable address, or the destination is off-subnet with no default
        gateway reachable on any of its own subnets.
        """
        for iface in self.ip_interfaces:
            assert iface.ipv4 and iface.netmask
            if same_subnet(iface.ipv4, dst_ip, iface.netmask):
                return dst_ip, iface

        gateway = self.config.gateway
        if not is_valid_ipv4(gateway):
            return None
        assert gateway
        for iface in self.ip_interfaces:
            assert iface.ipv4 and iface.netmask
            if same_subnet(iface.ipv4, gateway, iface.netmask):
                return gateway, iface
        return None

    def select_source_ip(self, dst_ip: str) -> str | None:
        """The address a packet to `dst_ip` would leave with, if it can leave."""
        hop = self.next_hop_for(dst_ip)
        return hop[1].ipv4 if hop else None

    def send_ipv4(
        self,
        packet: IPv4Packet,
        engine: "SimulationEngine",
        flow_id: str | None = None,
    ) -> list[Emission]:
        """Encapsulate and hand an IPv4 packet to the wire."""
        hop = self.next_hop_for(packet.dst_ip)
        if hop is None:
            if is_valid_ipv4(self.config.gateway):
                reason = (
                    f"default gateway {self.config.gateway} is not on any of this host's subnets"
                )
            elif not self.ip_interfaces:
                reason = "this host has no usable IP address"
            else:
                reason = "destination is on another subnet and no default gateway is configured"
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: cannot reach {packet.dst_ip} — {reason}",
                severity=Severity.ERROR,
                device=self,
            )
            return []

        next_ip, iface = hop
        assert iface.ipv4 and iface.netmask

        if is_broadcast_ip(next_ip, iface.ipv4, iface.netmask):
            dst_mac: str | None = BROADCAST_MAC
        else:
            dst_mac = engine.resolve_arp(self, next_ip, iface)

        if dst_mac is None:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: dropped packet to {packet.dst_ip} — "
                f"could not resolve MAC address of {next_ip}",
                severity=Severity.ERROR,
                device=self,
                interface=iface,
            )
            return []

        frame = EthernetFrame(
            src_mac=iface.mac,
            dst_mac=dst_mac,
            ethertype=EtherType.IPV4,
            payload=packet,
            flow_id=flow_id or next_flow_id(),
        )
        via = "" if next_ip == packet.dst_ip else f" via {next_ip}"
        engine.log(
            EventType.FRAME_SENT,
            f"{self.name}: sending {packet.protocol.value} to {packet.dst_ip}{via}",
            device=self,
            interface=iface,
            frame=frame,
        )
        return [Emission(interface_id=iface.id, frame=frame)]

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
                f"{self.name}: frame for {frame.dst_mac} is not for this NIC — discarded",
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
                    f"{self.name}: ARP request is for {arp.target_ip}, not me — ignored",
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )
                return []

            # Answering an ARP request also means caching the asker.
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

        # A reply we asked for: cache it so the waiting packet can go out.
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

        is_for_us = self.owns_ip(packet.dst_ip) or is_broadcast_ip(
            packet.dst_ip, in_interface.ipv4, in_interface.netmask
        )
        if not is_for_us:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: packet is addressed to {packet.dst_ip} — "
                "a host does not forward traffic, discarded",
                severity=Severity.WARNING,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        if packet.protocol is not IPProtocol.ICMP:
            return []

        icmp = packet.payload
        assert isinstance(icmp, IcmpMessage)

        if icmp.type is IcmpType.ECHO_REQUEST:
            engine.log(
                EventType.ICMP_REQUEST,
                f"{self.name}: received echo request from {packet.src_ip} (seq={icmp.sequence})",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            reply_packet = IPv4Packet(
                src_ip=packet.dst_ip,
                dst_ip=packet.src_ip,
                protocol=IPProtocol.ICMP,
                payload=icmp.echo_reply(),
                length=packet.length,
            )
            engine.log(
                EventType.ICMP_REPLY,
                f"{self.name}: generating echo reply to {packet.src_ip}",
                device=self,
                interface=in_interface,
            )
            # The reply is routed independently — which is why a server with a
            # missing default gateway can receive pings but never answer them.
            return self.send_ipv4(reply_packet, engine, flow_id=frame.flow_id)

        self.icmp_inbox.append((packet, icmp))
        engine.log(
            EventType.ICMP_ERROR if icmp.is_error else EventType.ICMP_REPLY,
            f"{self.name}: received {icmp.summary()} from {packet.src_ip}",
            severity=Severity.ERROR if icmp.is_error else Severity.SUCCESS,
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return []
