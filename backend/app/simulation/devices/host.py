"""Shared behaviour for end hosts (PCs and servers).

A host has no routing table. It uses the classic end-station decision every
networking course teaches: if the destination is inside my own subnet, send it
straight there; otherwise hand it to my default gateway. Getting either the
netmask or the gateway wrong therefore breaks connectivity for real.

Hosts also run applications. A port only answers when a service is listening on
it, names only resolve when a reachable DNS server holds the record, and a DHCP
client genuinely reconfigures its own interface from the lease it is given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..arp.packet import ArpOperation, ArpPacket
from ..core.addressing import (
    LIMITED_BROADCAST,
    is_broadcast_ip,
    is_valid_ipv4,
    same_subnet,
)
from ..core.events import EventType, Severity
from ..core.mac import BROADCAST_MAC
from ..core.models import DeviceConfig, Emission, Interface
from ..dhcp.message import DhcpLease, DhcpMessage, DhcpMessageType
from ..dhcp.pool import DhcpPool
from ..dns.message import DnsQuery, DnsResponse
from ..dns.records import DnsRecordType, DnsZone, normalize_name
from ..ethernet.frame import EtherType, EthernetFrame, next_flow_id
from ..icmp.message import IcmpCode, IcmpMessage, IcmpType
from ..ipv4.packet import DEFAULT_TTL, IPProtocol, IPv4Packet
from ..transport.segment import (
    TcpFlag,
    TransportProtocol,
    TransportSegment,
    next_ephemeral_port,
)
from ..transport.services import (
    DHCP_CLIENT_PORT,
    DHCP_SERVER_PORT,
    DNS_PORT,
    VPN_PORT,
    describe_port,
)
from . import app_services
from .base import Device

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine

#: Nominal byte counts, so the inspector shows something plausible.
TCP_SEGMENT_BYTES = 40
UDP_DATAGRAM_BYTES = 60


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
        #: ICMP messages addressed to us, drained by ping and traceroute.
        self.icmp_inbox: list[tuple[IPv4Packet, IcmpMessage]] = []
        #: TCP/UDP segments addressed to us, drained by the connect command.
        self.transport_inbox: list[tuple[IPv4Packet, TransportSegment]] = []
        #: DNS answers we are waiting on, matched by transaction id.
        self.dns_inbox: list[DnsResponse] = []
        #: Names this host has already resolved.
        self.dns_cache: dict[str, str] = {}

        #: Populated by the loader from config, when this host serves them.
        self.dns_zone = DnsZone()
        self.dhcp_pool: DhcpPool | None = None

        #: DHCP offers seen mid-exchange, and the lease finally applied.
        self.dhcp_offers: list[DhcpMessage] = []
        self.dhcp_lease: DhcpLease | None = None
        #: Set when DHCP changed this host's addressing, so the caller knows to
        #: write the new configuration back into the topology document.
        self.dhcp_changed = False
        #: On a VPN gateway: tunnel address -> the client's real address.
        #: Learned when a tunnelled packet arrives, and used to send replies
        #: back through the tunnel instead of letting them route around it.
        self.vpn_peers: dict[str, str] = {}

    @property
    def primary_interface(self) -> Interface | None:
        return self.interfaces[0] if self.interfaces else None

    @property
    def first_enabled_interface(self) -> Interface | None:
        return next((i for i in self.interfaces if i.enabled), None)

    # -- listening sockets -----------------------------------------------

    def is_listening(self, protocol: TransportProtocol, port: int) -> bool:
        return any(
            service.enabled
            and service.port == port
            and service.protocol.upper() == protocol.value
            for service in self.config.services
        )

    @property
    def open_ports(self) -> list[tuple[str, int, str]]:
        """(protocol, port, service name) for everything currently listening."""
        return [
            (service.protocol.upper(), service.port, service.name)
            for service in self.config.services
            if service.enabled
        ]

    @property
    def serves_dns(self) -> bool:
        # Listening is enough. A server with an empty zone still answers — with
        # NXDOMAIN — which is a very different fault from one that never replies.
        return self.is_listening(TransportProtocol.UDP, DNS_PORT)

    @property
    def serves_dhcp(self) -> bool:
        return (
            self.is_listening(TransportProtocol.UDP, DHCP_SERVER_PORT)
            and self.dhcp_pool is not None
        )

    @property
    def is_vpn_gateway(self) -> bool:
        vpn = self.config.vpn
        return bool(
            vpn and vpn.is_gateway and vpn.enabled
        ) and self.is_listening(TransportProtocol.UDP, VPN_PORT)

    @property
    def has_active_tunnel(self) -> bool:
        """True for a client configured to tunnel somewhere."""
        vpn = self.config.vpn
        return bool(vpn and vpn.enabled and not vpn.is_gateway and vpn.server)

    @property
    def tunnel_ip(self) -> str | None:
        vpn = self.config.vpn
        if vpn and vpn.enabled and vpn.tunnel_ip and is_valid_ipv4(vpn.tunnel_ip):
            return vpn.tunnel_ip
        return None

    def accepts_ip(self, ip: str) -> bool:
        """Addresses this host answers for, including its tunnel address."""
        return self.owns_ip(ip) or (self.tunnel_ip is not None and ip == self.tunnel_ip)

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
        tunnelled = app_services.maybe_tunnel(self, packet, engine, flow_id)
        if tunnelled is not None:
            return tunnelled

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
            f"{self.name}: sending {_describe_payload(packet)} to {packet.dst_ip}{via}",
            device=self,
            interface=iface,
            frame=frame,
        )
        return [Emission(interface_id=iface.id, frame=frame)]

    def send_broadcast(
        self,
        payload: Any,
        protocol: IPProtocol,
        engine: "SimulationEngine",
        src_ip: str = "0.0.0.0",
        flow_id: str | None = None,
    ) -> list[Emission]:
        """Put a packet on the local wire without needing an address first.

        DHCP depends on this: a client with no lease cannot route anything, so
        DISCOVER goes out as a link-layer broadcast from 0.0.0.0.
        """
        iface = self.first_enabled_interface
        if iface is None:
            engine.log(
                EventType.PACKET_DROPPED,
                f"{self.name}: no enabled interface to broadcast from",
                severity=Severity.ERROR,
                device=self,
            )
            return []

        packet = IPv4Packet(
            src_ip=src_ip,
            dst_ip=LIMITED_BROADCAST,
            protocol=protocol,
            payload=payload,
            length=UDP_DATAGRAM_BYTES,
        )
        frame = EthernetFrame(
            src_mac=iface.mac,
            dst_mac=BROADCAST_MAC,
            ethertype=EtherType.IPV4,
            payload=packet,
            flow_id=flow_id or next_flow_id(),
        )
        engine.log(
            EventType.FRAME_SENT,
            f"{self.name}: broadcasting {_describe_payload(packet)}",
            device=self,
            interface=iface,
            frame=frame,
        )
        return [Emission(interface_id=iface.id, frame=frame)]

    def send_segment(
        self,
        dst_ip: str,
        segment: TransportSegment,
        engine: "SimulationEngine",
        flow_id: str | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> list[Emission]:
        source_ip = self.select_source_ip(dst_ip)
        if source_ip is None:
            source_ip = self.ip_interfaces[0].ipv4 if self.ip_interfaces else "0.0.0.0"
        packet = IPv4Packet(
            src_ip=source_ip or "0.0.0.0",
            dst_ip=dst_ip,
            protocol=(
                IPProtocol.TCP if segment.is_tcp else IPProtocol.UDP
            ),
            payload=segment,
            ttl=ttl,
            length=TCP_SEGMENT_BYTES if segment.is_tcp else UDP_DATAGRAM_BYTES,
        )
        return self.send_ipv4(packet, engine, flow_id)

    # -- DNS client -------------------------------------------------------

    def resolve_name(
        self,
        name: str,
        engine: "SimulationEngine",
        record_type: DnsRecordType = DnsRecordType.A,
    ) -> DnsResponse | None:
        """Ask our configured DNS server to turn a name into an address.

        Returns None when we never got an answer at all — no server
        configured, or the query never made it there and back.
        """
        wanted = normalize_name(name)

        if record_type is DnsRecordType.A:
            cached = self.dns_cache.get(wanted)
            if cached:
                engine.log(
                    EventType.DNS_CACHE_HIT,
                    f"{self.name}: {wanted} is already cached as {cached}",
                    device=self,
                )
                from ..dns.records import DnsRecord, DnsStatus

                record = DnsRecord(name=wanted, type=DnsRecordType.A, value=cached)
                return DnsResponse(
                    name=wanted,
                    type=DnsRecordType.A,
                    status=DnsStatus.NOERROR,
                    transaction_id=0,
                    address=cached,
                    answers=[record],
                    chain=[record],
                )

        server = self.config.dns_server
        if not is_valid_ipv4(server):
            engine.log(
                EventType.DNS_NO_SERVER,
                f"{self.name}: cannot resolve {wanted} — no DNS server is configured",
                severity=Severity.ERROR,
                device=self,
            )
            return None
        assert server

        query = DnsQuery(name=wanted, type=record_type)
        segment = TransportSegment(
            protocol=TransportProtocol.UDP,
            src_port=next_ephemeral_port(),
            dst_port=DNS_PORT,
            payload=query,
        )

        self.dns_inbox.clear()
        engine.log(
            EventType.DNS_QUERY,
            f"{self.name}: asking {server} for {record_type.value} {wanted}",
            device=self,
        )
        emissions = self.send_segment(server, segment, engine)
        if not emissions:
            return None
        engine.run(self, emissions)

        response = next(
            (r for r in self.dns_inbox if r.transaction_id == query.transaction_id),
            None,
        )
        if response is None:
            engine.log(
                EventType.DNS_NO_SERVER,
                f"{self.name}: no answer from DNS server {server} for {wanted}",
                severity=Severity.ERROR,
                device=self,
            )
            return None

        if response.ok and response.address:
            self.dns_cache[wanted] = response.address
        return response

    def resolve_target(
        self, target: str, engine: "SimulationEngine"
    ) -> tuple[str | None, DnsResponse | None]:
        """Accept either a literal address or a name.

        Returns (address, dns_response). The response is None when `target` was
        already an address, so callers can tell "no DNS involved" from
        "DNS said no".
        """
        if is_valid_ipv4(target):
            return target, None
        response = self.resolve_name(target, engine)
        if response is None:
            return None, None
        return (response.address if response.ok else None), response

    # -- DHCP client ------------------------------------------------------

    def request_dhcp_lease(self, engine: "SimulationEngine") -> DhcpLease | None:
        """Run a full DISCOVER / OFFER / REQUEST / ACK exchange."""
        return app_services.run_dhcp_client(self, engine)

    def apply_lease(self, lease: DhcpLease, engine: "SimulationEngine") -> None:
        iface = self.first_enabled_interface
        if iface is None:
            return
        iface.ipv4 = lease.ip
        iface.netmask = lease.netmask
        self.config.gateway = lease.gateway
        self.config.dns_server = lease.dns
        self.dhcp_lease = lease
        self.dhcp_changed = True
        engine.log(
            EventType.DHCP_APPLIED,
            f"{self.name}: applied {lease.summary()} to {iface.name}",
            severity=Severity.SUCCESS,
            device=self,
            interface=iface,
        )

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
            # A VPN gateway answers for the tunnel addresses of its clients —
            # proxy ARP — so the internal network sends their traffic to it.
            proxying = arp.target_ip in self.vpn_peers
            if in_interface.ipv4 != arp.target_ip and not proxying:
                engine.log(
                    EventType.FRAME_DROPPED,
                    f"{self.name}: ARP request is for {arp.target_ip}, not me — ignored",
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )
                return []
            if proxying:
                engine.log(
                    EventType.ARP_REPLY,
                    f"{self.name}: answering for tunnel client {arp.target_ip} "
                    "on its behalf",
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )

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

        is_for_us = self.accepts_ip(packet.dst_ip) or is_broadcast_ip(
            packet.dst_ip, in_interface.ipv4, in_interface.netmask
        )
        if not is_for_us:
            # A gateway does forward one thing: traffic for a tunnel client,
            # which goes back into the tunnel it came out of.
            if packet.dst_ip in self.vpn_peers:
                return app_services.forward_into_tunnel(
                    self, packet, frame, in_interface, engine
                )
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

        if packet.protocol is IPProtocol.ICMP:
            return self._handle_icmp(packet, frame, in_interface, engine)
        if packet.protocol in (IPProtocol.TCP, IPProtocol.UDP):
            return self._handle_transport(packet, frame, in_interface, engine)
        return []

    def _handle_icmp(
        self,
        packet: IPv4Packet,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
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

    def _handle_transport(
        self,
        packet: IPv4Packet,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        segment = packet.payload
        assert isinstance(segment, TransportSegment)

        if segment.is_tcp:
            return self._handle_tcp(packet, segment, frame, in_interface, engine)
        return self._handle_udp(packet, segment, frame, in_interface, engine)

    def _handle_tcp(
        self,
        packet: IPv4Packet,
        segment: TransportSegment,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        port = describe_port(TransportProtocol.TCP, segment.dst_port)

        if segment.flag is TcpFlag.SYN:
            if self.is_listening(TransportProtocol.TCP, segment.dst_port):
                engine.log(
                    EventType.PORT_OPEN,
                    f"{self.name}: {port} is open — accepting the connection",
                    severity=Severity.SUCCESS,
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )
                return self._reply_tcp(packet, segment, TcpFlag.SYN_ACK, frame, engine)

            engine.log(
                EventType.PORT_CLOSED,
                f"{self.name}: nothing is listening on {port} — refusing with RST",
                severity=Severity.WARNING,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return self._reply_tcp(packet, segment, TcpFlag.RST, frame, engine)

        if segment.flag in (TcpFlag.SYN_ACK, TcpFlag.RST):
            self.transport_inbox.append((packet, segment))
            engine.log(
                EventType.TCP_SYN_ACK if segment.flag is TcpFlag.SYN_ACK else EventType.TCP_RST,
                f"{self.name}: received {segment.flag.value} from {packet.src_ip}:{segment.src_port}",
                severity=(
                    Severity.SUCCESS if segment.flag is TcpFlag.SYN_ACK else Severity.ERROR
                ),
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        if segment.flag is TcpFlag.ACK:
            engine.log(
                EventType.TCP_ESTABLISHED,
                f"{self.name}: connection from {packet.src_ip} on {port} is established",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=frame,
            )
        return []

    def _reply_tcp(
        self,
        packet: IPv4Packet,
        segment: TransportSegment,
        flag: TcpFlag,
        frame: EthernetFrame,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        src_port, dst_port = segment.reply_ports()
        reply = TransportSegment(
            protocol=TransportProtocol.TCP,
            src_port=src_port,
            dst_port=dst_port,
            flag=flag,
        )
        reply_packet = IPv4Packet(
            src_ip=packet.dst_ip,
            dst_ip=packet.src_ip,
            protocol=IPProtocol.TCP,
            payload=reply,
            length=TCP_SEGMENT_BYTES,
        )
        return self.send_ipv4(reply_packet, engine, flow_id=frame.flow_id)

    def _handle_udp(
        self,
        packet: IPv4Packet,
        segment: TransportSegment,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        # Application dispatch. Each of these only fires when the matching
        # service is actually enabled on this device.
        if segment.dst_port == DNS_PORT and self.serves_dns:
            return app_services.serve_dns(self, packet, segment, frame, in_interface, engine)

        if segment.dst_port == DHCP_SERVER_PORT and self.serves_dhcp:
            return app_services.serve_dhcp(self, packet, segment, frame, in_interface, engine)

        if segment.dst_port == DHCP_CLIENT_PORT:
            return app_services.receive_dhcp_reply(self, packet, segment, frame, in_interface, engine)

        # Both ends of a tunnel unwrap what arrives on the tunnel port.
        if segment.dst_port == VPN_PORT and (
            self.is_vpn_gateway or self.has_active_tunnel
        ):
            return app_services.decapsulate(self, packet, segment, frame, in_interface, engine)

        if segment.dst_port == DNS_PORT and isinstance(segment.payload, DnsResponse):
            # Unusual, but keeps a response arriving on 53 from being dropped.
            self.dns_inbox.append(segment.payload)
            return []

        if isinstance(segment.payload, DnsResponse):
            self.dns_inbox.append(segment.payload)
            engine.log(
                EventType.DNS_RESPONSE,
                f"{self.name}: {segment.payload.summary()}",
                severity=(
                    Severity.SUCCESS if segment.payload.ok else Severity.ERROR
                ),
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        if self.is_listening(TransportProtocol.UDP, segment.dst_port):
            self.transport_inbox.append((packet, segment))
            engine.log(
                EventType.UDP_DATAGRAM,
                f"{self.name}: received datagram on "
                f"{describe_port(TransportProtocol.UDP, segment.dst_port)}",
                severity=Severity.SUCCESS,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []

        engine.log(
            EventType.PORT_CLOSED,
            f"{self.name}: nothing is listening on "
            f"{describe_port(TransportProtocol.UDP, segment.dst_port)} — "
            "returning port unreachable",
            severity=Severity.WARNING,
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return self._send_icmp_unreachable(packet, frame, engine)

    def _send_icmp_unreachable(
        self,
        packet: IPv4Packet,
        frame: EthernetFrame,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        error = IPv4Packet(
            src_ip=packet.dst_ip,
            dst_ip=packet.src_ip,
            protocol=IPProtocol.ICMP,
            payload=IcmpMessage(
                type=IcmpType.DESTINATION_UNREACHABLE,
                code=IcmpCode.PORT_UNREACHABLE,
            ),
        )
        return self.send_ipv4(error, engine, flow_id=frame.flow_id)

    # -- runtime state ----------------------------------------------------

    def state(self) -> dict[str, Any]:
        base = super().state()
        base["dns_cache"] = dict(self.dns_cache)
        if self.dhcp_pool is not None:
            base["dhcp_leases"] = self.dhcp_pool.to_dict()

        # Emitted whenever DHCP touched our addressing, including a release —
        # where every field is None, which is exactly what must be written back.
        if self.dhcp_changed:
            iface = self.first_enabled_interface
            lease = self.dhcp_lease
            base["assigned"] = {
                "interface_id": iface.id if iface else None,
                "ipv4": lease.ip if lease else None,
                "netmask": lease.netmask if lease else None,
                "gateway": lease.gateway if lease else None,
                "dns_server": lease.dns if lease else None,
                "lease_seconds": lease.lease_seconds if lease else None,
                "server_ip": lease.server_ip if lease else None,
            }
        return base

    def load_state(self, state: dict[str, Any] | None) -> None:
        super().load_state(state)
        if not state:
            return
        self.dns_cache = dict(state.get("dns_cache") or {})


def _describe_payload(packet: IPv4Packet) -> str:
    """Short protocol label used in FRAME_SENT messages."""
    payload = packet.payload
    if isinstance(payload, TransportSegment):
        if isinstance(payload.payload, DnsQuery):
            return f"DNS query for {payload.payload.name}"
        if isinstance(payload.payload, DnsResponse):
            return "DNS response"
        if isinstance(payload.payload, DhcpMessage):
            return f"DHCP {payload.payload.type.value}"
        if isinstance(payload.payload, IPv4Packet):
            return "tunnelled IPv4"
        return payload.summary()
    if isinstance(payload, IcmpMessage):
        return payload.summary()
    return packet.protocol.value


__all__ = ["Host", "DhcpMessageType"]
