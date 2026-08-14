"""Server-side application behaviour for hosts: DNS, DHCP and VPN tunnelling.

These live outside `Host` so that class stays about being a network node, and
so each protocol exchange can be read start to finish in one place. Every
function here is driven by real configuration — a DNS server with no records
answers NXDOMAIN, a disabled service never replies at all.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ..core.addressing import ip_in_network, is_valid_ipv4, is_valid_netmask
from ..core.events import EventType, Severity
from ..core.mac import normalize_mac
from ..core.models import Emission, Interface
from ..dhcp.message import DhcpLease, DhcpMessage, DhcpMessageType
from ..dhcp.server import handle as dhcp_handle
from ..dns.message import DnsQuery
from ..dns.records import DnsStatus
from ..dns.server import answer_query
from ..ethernet.frame import EthernetFrame
from ..ipv4.packet import IPProtocol, IPv4Packet
from ..transport.segment import (
    TransportProtocol,
    TransportSegment,
    next_ephemeral_port,
)
from ..transport.services import DHCP_CLIENT_PORT, DHCP_SERVER_PORT, DNS_PORT, VPN_PORT

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine
    from .host import Host


# -- DNS ------------------------------------------------------------------


def serve_dns(
    host: "Host",
    packet: IPv4Packet,
    segment: TransportSegment,
    frame: EthernetFrame,
    in_interface: Interface,
    engine: "SimulationEngine",
) -> list[Emission]:
    query = segment.payload
    if not isinstance(query, DnsQuery):
        return []

    engine.log(
        EventType.DNS_QUERY,
        f"{host.name}: received query for {query.type.value} {query.name} "
        f"from {packet.src_ip}",
        device=host,
        interface=in_interface,
        frame=frame,
    )

    response = answer_query(host.dns_zone, query)

    if response.ok:
        detail = response.address or f"{len(response.answers)} record(s)"
        # Show the CNAME trail, because that is usually where the fault is.
        if len(response.chain) > 1:
            trail = " → ".join(record.value for record in response.chain)
            detail = f"{detail} (via {trail})"
        engine.log(
            EventType.DNS_RESPONSE,
            f"{host.name}: answering {query.name} with {detail}",
            severity=Severity.SUCCESS,
            device=host,
            interface=in_interface,
        )
    else:
        engine.log(
            EventType.DNS_NXDOMAIN,
            f"{host.name}: {response.status.value} for {query.name}"
            + (f" — {response.detail}" if response.detail else ""),
            severity=Severity.ERROR,
            device=host,
            interface=in_interface,
        )

    reply_segment = TransportSegment(
        protocol=TransportProtocol.UDP,
        src_port=DNS_PORT,
        dst_port=segment.src_port,
        payload=response,
    )
    reply_packet = IPv4Packet(
        src_ip=packet.dst_ip,
        dst_ip=packet.src_ip,
        protocol=IPProtocol.UDP,
        payload=reply_segment,
    )
    return host.send_ipv4(reply_packet, engine, flow_id=frame.flow_id)


# -- DHCP -----------------------------------------------------------------


_RECEIVED_EVENT = {
    DhcpMessageType.DISCOVER: EventType.DHCP_DISCOVER,
    DhcpMessageType.REQUEST: EventType.DHCP_REQUEST,
    DhcpMessageType.RELEASE: EventType.DHCP_REQUEST,
}

_SENT_EVENT = {
    DhcpMessageType.OFFER: EventType.DHCP_OFFER,
    DhcpMessageType.ACK: EventType.DHCP_ACK,
    DhcpMessageType.NAK: EventType.DHCP_NAK,
}


def serve_dhcp(
    host: "Host",
    packet: IPv4Packet,
    segment: TransportSegment,
    frame: EthernetFrame,
    in_interface: Interface,
    engine: "SimulationEngine",
) -> list[Emission]:
    message = segment.payload
    if not isinstance(message, DhcpMessage) or host.dhcp_pool is None:
        return []

    engine.log(
        _RECEIVED_EVENT.get(message.type, EventType.UDP_DATAGRAM),
        f"{host.name}: received DHCP {message.type.value} from {message.client_mac}",
        device=host,
        interface=in_interface,
        frame=frame,
    )

    reply = dhcp_handle(message, host.dhcp_pool, in_interface.ipv4)
    if reply is None:
        return []

    if reply.type is DhcpMessageType.NAK:
        engine.log(
            EventType.DHCP_NAK,
            f"{host.name}: refusing {message.client_mac} — {reply.reason}",
            severity=Severity.ERROR,
            device=host,
            interface=in_interface,
        )
    else:
        assert reply.lease
        engine.log(
            _SENT_EVENT[reply.type],
            f"{host.name}: {reply.type.value} {reply.lease.summary()} "
            f"to {message.client_mac}",
            severity=Severity.SUCCESS,
            device=host,
            interface=in_interface,
        )

    out = TransportSegment(
        protocol=TransportProtocol.UDP,
        src_port=DHCP_SERVER_PORT,
        dst_port=DHCP_CLIENT_PORT,
        payload=reply,
    )
    # The client still has no address, so the reply has to go out as a broadcast.
    return host.send_broadcast(
        out,
        IPProtocol.UDP,
        engine,
        src_ip=in_interface.ipv4 or "0.0.0.0",
        flow_id=frame.flow_id,
    )


def receive_dhcp_reply(
    host: "Host",
    packet: IPv4Packet,
    segment: TransportSegment,
    frame: EthernetFrame,
    in_interface: Interface,
    engine: "SimulationEngine",
) -> list[Emission]:
    message = segment.payload
    if not isinstance(message, DhcpMessage):
        return []

    # Everyone on the segment sees the broadcast; only the addressed client acts.
    if normalize_mac(message.client_mac) != normalize_mac(in_interface.mac):
        return []

    host.dhcp_offers.append(message)
    engine.log(
        _SENT_EVENT.get(message.type, EventType.UDP_DATAGRAM),
        f"{host.name}: received DHCP {message.type.value}"
        + (f" — {message.lease.summary()}" if message.lease else "")
        + (f" ({message.reason})" if message.reason else ""),
        severity=(
            Severity.ERROR if message.type is DhcpMessageType.NAK else Severity.SUCCESS
        ),
        device=host,
        interface=in_interface,
        frame=frame,
    )
    return []


def run_dhcp_client(host: "Host", engine: "SimulationEngine") -> DhcpLease | None:
    """Perform DISCOVER / OFFER / REQUEST / ACK and apply what comes back."""
    interface = host.first_enabled_interface
    if interface is None:
        engine.log(
            EventType.PACKET_DROPPED,
            f"{host.name}: no enabled interface to request a lease on",
            severity=Severity.ERROR,
            device=host,
        )
        return None

    discover = DhcpMessage(type=DhcpMessageType.DISCOVER, client_mac=interface.mac)
    host.dhcp_offers.clear()
    engine.log(
        EventType.DHCP_DISCOVER,
        f"{host.name}: broadcasting DHCP DISCOVER from {interface.mac}",
        device=host,
        interface=interface,
    )
    emissions = host.send_broadcast(
        TransportSegment(
            protocol=TransportProtocol.UDP,
            src_port=DHCP_CLIENT_PORT,
            dst_port=DHCP_SERVER_PORT,
            payload=discover,
        ),
        IPProtocol.UDP,
        engine,
    )
    if not emissions:
        return None
    engine.run(host, emissions)

    offer = next(
        (m for m in host.dhcp_offers if m.type is DhcpMessageType.OFFER and m.lease),
        None,
    )
    if offer is None:
        refusal = next(
            (m for m in host.dhcp_offers if m.type is DhcpMessageType.NAK), None
        )
        if refusal is None:
            engine.log(
                EventType.DHCP_NAK,
                f"{host.name}: no DHCP server answered the DISCOVER",
                severity=Severity.ERROR,
                device=host,
                interface=interface,
            )
        return None

    assert offer.lease
    request = DhcpMessage(
        type=DhcpMessageType.REQUEST,
        client_mac=interface.mac,
        transaction_id=offer.transaction_id,
        lease=offer.lease,
    )
    host.dhcp_offers.clear()
    engine.log(
        EventType.DHCP_REQUEST,
        f"{host.name}: requesting {offer.lease.ip}",
        device=host,
        interface=interface,
    )
    engine.run(
        host,
        host.send_broadcast(
            TransportSegment(
                protocol=TransportProtocol.UDP,
                src_port=DHCP_CLIENT_PORT,
                dst_port=DHCP_SERVER_PORT,
                payload=request,
            ),
            IPProtocol.UDP,
            engine,
        ),
    )

    acknowledged = next(
        (m for m in host.dhcp_offers if m.type is DhcpMessageType.ACK and m.lease), None
    )
    if acknowledged is None or acknowledged.lease is None:
        engine.log(
            EventType.DHCP_NAK,
            f"{host.name}: the request for {offer.lease.ip} was never acknowledged",
            severity=Severity.ERROR,
            device=host,
            interface=interface,
        )
        return None

    host.apply_lease(acknowledged.lease, engine)
    return acknowledged.lease


def release_dhcp_lease(host: "Host", engine: "SimulationEngine") -> bool:
    interface = host.first_enabled_interface
    if interface is None or host.dhcp_lease is None:
        return False

    engine.run(
        host,
        host.send_broadcast(
            TransportSegment(
                protocol=TransportProtocol.UDP,
                src_port=DHCP_CLIENT_PORT,
                dst_port=DHCP_SERVER_PORT,
                payload=DhcpMessage(
                    type=DhcpMessageType.RELEASE, client_mac=interface.mac
                ),
            ),
            IPProtocol.UDP,
            engine,
            src_ip=interface.ipv4 or "0.0.0.0",
        ),
    )

    interface.ipv4 = None
    host.config.gateway = None
    host.config.dns_server = None
    host.dhcp_lease = None
    host.dhcp_changed = True
    host.dns_cache.clear()
    engine.log(
        EventType.DHCP_APPLIED,
        f"{host.name}: released its lease — {interface.name} has no address now",
        severity=Severity.WARNING,
        device=host,
        interface=interface,
    )
    return True


# -- VPN ------------------------------------------------------------------


def maybe_tunnel(
    host: "Host",
    packet: IPv4Packet,
    engine: "SimulationEngine",
    flow_id: str | None,
) -> list[Emission] | None:
    """Wrap a packet for the tunnel, or return None to send it normally.

    Only traffic aimed at the network behind the gateway is tunnelled. The
    outer packet is ordinary UDP, which is the whole point: a firewall in the
    middle sees UDP/1194 and nothing of what it carries.
    """
    vpn = host.config.vpn
    if vpn is None or not vpn.enabled or vpn.is_gateway:
        return None
    if not (vpn.server and vpn.remote_network and vpn.remote_netmask):
        return None
    if not (
        is_valid_ipv4(vpn.server)
        and is_valid_ipv4(vpn.remote_network)
        and is_valid_netmask(vpn.remote_netmask)
    ):
        return None

    # Never tunnel the tunnel: this is what stops the recursion.
    if packet.dst_ip == vpn.server:
        return None
    inner = packet.payload
    if isinstance(inner, TransportSegment) and inner.dst_port == VPN_PORT:
        return None
    if not ip_in_network(packet.dst_ip, vpn.remote_network, vpn.remote_netmask):
        return None

    # Inside the tunnel the client uses its tunnel address, so the far end sees
    # a source on its own network and its reply comes back through the tunnel.
    inner = packet
    if vpn.tunnel_ip and is_valid_ipv4(vpn.tunnel_ip):
        inner = replace(packet, src_ip=vpn.tunnel_ip)

    engine.log(
        EventType.VPN_ENCAPSULATE,
        f"{host.name}: wrapping the packet for {packet.dst_ip} inside a tunnel "
        f"to {vpn.server}"
        + (f" as {vpn.tunnel_ip}" if inner is not packet else ""),
        device=host,
    )
    outer_segment = TransportSegment(
        protocol=TransportProtocol.UDP,
        src_port=next_ephemeral_port(),
        dst_port=VPN_PORT,
        payload=inner,
    )
    source_ip = host.select_source_ip(vpn.server)
    outer = IPv4Packet(
        src_ip=source_ip or (host.ip_interfaces[0].ipv4 if host.ip_interfaces else "0.0.0.0"),
        dst_ip=vpn.server,
        protocol=IPProtocol.UDP,
        payload=outer_segment,
        length=packet.length + 28,
    )
    # Goes back through send_ipv4, where the guard above returns None.
    return host.send_ipv4(outer, engine, flow_id)


def decapsulate(
    host: "Host",
    packet: IPv4Packet,
    segment: TransportSegment,
    frame: EthernetFrame,
    in_interface: Interface,
    engine: "SimulationEngine",
) -> list[Emission]:
    """Unwrap a tunnelled packet on the gateway and forward what was inside."""
    inner = segment.payload
    if not isinstance(inner, IPv4Packet):
        engine.log(
            EventType.PACKET_DROPPED,
            f"{host.name}: tunnel datagram carried no IPv4 packet — discarded",
            severity=Severity.WARNING,
            device=host,
            interface=in_interface,
            frame=frame,
        )
        return []

    # Remember who is on the far side of this tunnel, so replies for their
    # tunnel address can be sent back into it rather than routed around it.
    if host.is_vpn_gateway and inner.src_ip != packet.src_ip:
        host.vpn_peers[inner.src_ip] = packet.src_ip

    engine.log(
        EventType.VPN_DECAPSULATE,
        f"{host.name}: unwrapped a tunnelled packet "
        f"{inner.src_ip} → {inner.dst_ip}",
        severity=Severity.SUCCESS,
        device=host,
        interface=in_interface,
        frame=frame,
    )

    if host.accepts_ip(inner.dst_ip):
        # The tunnel terminated at its own destination — this is the reply
        # arriving back at the client.
        unwrapped = EthernetFrame(
            src_mac=frame.src_mac,
            dst_mac=in_interface.mac,
            ethertype=frame.ethertype,
            payload=inner,
            flow_id=frame.flow_id,
        )
        return host._handle_ipv4(unwrapped, in_interface, engine)

    return host.send_ipv4(inner, engine, flow_id=frame.flow_id)


def forward_into_tunnel(
    host: "Host",
    packet: IPv4Packet,
    frame: EthernetFrame,
    in_interface: Interface,
    engine: "SimulationEngine",
) -> list[Emission]:
    """Send a packet destined for a tunnel client back through its tunnel."""
    peer = host.vpn_peers.get(packet.dst_ip)
    if peer is None:
        return []

    engine.log(
        EventType.VPN_ENCAPSULATE,
        f"{host.name}: {packet.dst_ip} is a tunnel client — wrapping the reply "
        f"and sending it to {peer}",
        device=host,
        interface=in_interface,
        frame=frame,
    )
    outer_segment = TransportSegment(
        protocol=TransportProtocol.UDP,
        src_port=VPN_PORT,
        dst_port=VPN_PORT,
        payload=packet,
    )
    source_ip = host.select_source_ip(peer) or (
        host.ip_interfaces[0].ipv4 if host.ip_interfaces else "0.0.0.0"
    )
    outer = IPv4Packet(
        src_ip=source_ip or "0.0.0.0",
        dst_ip=peer,
        protocol=IPProtocol.UDP,
        payload=outer_segment,
        length=packet.length + 28,
    )
    return host.send_ipv4(outer, engine, flow_id=frame.flow_id)


__all__ = [
    "decapsulate",
    "forward_into_tunnel",
    "maybe_tunnel",
    "receive_dhcp_reply",
    "release_dhcp_lease",
    "run_dhcp_client",
    "serve_dhcp",
    "serve_dns",
    "DnsStatus",
]
