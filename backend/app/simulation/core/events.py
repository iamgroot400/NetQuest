"""Simulation events.

The event trace is the single output the UI replays: it drives the packet
animation, the step-by-step log, and the packet inspector. Everything the
engine does that a learner should be able to see must produce an event.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    # Lifecycle
    COMMAND = "command"
    INFO = "info"

    # Layer 2
    FRAME_SENT = "frame_sent"
    FRAME_TRANSMITTED = "frame_transmitted"
    FRAME_RECEIVED = "frame_received"
    FRAME_DROPPED = "frame_dropped"
    FRAME_FLOODED = "frame_flooded"
    MAC_LEARNED = "mac_learned"

    # ARP
    ARP_REQUEST = "arp_request"
    ARP_REPLY = "arp_reply"
    ARP_CACHE_HIT = "arp_cache_hit"
    ARP_RESOLVED = "arp_resolved"
    ARP_FAILED = "arp_failed"

    # Layer 3
    ROUTE_LOOKUP = "route_lookup"
    ROUTE_MISS = "route_miss"
    TTL_DECREMENT = "ttl_decrement"
    TTL_EXPIRED = "ttl_expired"
    PACKET_DELIVERED = "packet_delivered"
    PACKET_DROPPED = "packet_dropped"

    # ICMP
    ICMP_REQUEST = "icmp_request"
    ICMP_REPLY = "icmp_reply"
    ICMP_ERROR = "icmp_error"

    # Layer 4
    SEGMENT_SENT = "segment_sent"
    TCP_SYN = "tcp_syn"
    TCP_SYN_ACK = "tcp_syn_ack"
    TCP_RST = "tcp_rst"
    TCP_ESTABLISHED = "tcp_established"
    UDP_DATAGRAM = "udp_datagram"
    PORT_OPEN = "port_open"
    PORT_CLOSED = "port_closed"

    # DNS
    DNS_QUERY = "dns_query"
    DNS_RESPONSE = "dns_response"
    DNS_NXDOMAIN = "dns_nxdomain"
    DNS_CACHE_HIT = "dns_cache_hit"
    DNS_NO_SERVER = "dns_no_server"

    # DHCP
    DHCP_DISCOVER = "dhcp_discover"
    DHCP_OFFER = "dhcp_offer"
    DHCP_REQUEST = "dhcp_request"
    DHCP_ACK = "dhcp_ack"
    DHCP_NAK = "dhcp_nak"
    DHCP_APPLIED = "dhcp_applied"

    # Firewall
    FIREWALL_ALLOW = "firewall_allow"
    FIREWALL_DENY = "firewall_deny"

    # NAT
    NAT_TRANSLATE = "nat_translate"
    NAT_UNTRANSLATE = "nat_untranslate"
    NAT_NO_ENTRY = "nat_no_entry"

    # VPN
    VPN_ENCAPSULATE = "vpn_encapsulate"
    VPN_DECAPSULATE = "vpn_decapsulate"


class Severity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class SimEvent:
    seq: int
    type: EventType
    message: str
    severity: Severity = Severity.INFO
    device_id: str | None = None
    device_name: str | None = None
    interface_id: str | None = None
    interface_name: str | None = None
    # Set only on FRAME_TRANSMITTED: the wire the frame crossed and its direction.
    link_id: str | None = None
    from_device_id: str | None = None
    to_device_id: str | None = None
    frame_uid: str | None = None
    flow_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        data["severity"] = self.severity.value
        return data


@dataclass
class PacketSnapshot:
    """Everything the packet inspector shows about one frame on the wire."""

    frame_uid: str
    flow_id: str
    summary: str
    ethertype: str
    src_mac: str
    dst_mac: str
    protocol: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    ttl: int | None = None
    length: int | None = None
    icmp_type: str | None = None
    icmp_code: str | None = None
    icmp_sequence: int | None = None
    icmp_identifier: int | None = None
    arp_operation: str | None = None
    arp_sender_ip: str | None = None
    arp_target_ip: str | None = None
    arp_sender_mac: str | None = None
    arp_target_mac: str | None = None

    # Layer 4
    transport_protocol: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    tcp_flag: str | None = None

    # Application payloads, surfaced so the inspector can show what was asked
    # and what came back rather than an opaque blob.
    dns_query_name: str | None = None
    dns_query_type: str | None = None
    dns_status: str | None = None
    dns_answers: list[str] = field(default_factory=list)
    dhcp_type: str | None = None
    dhcp_offered_ip: str | None = None

    #: True when this packet carries another IPv4 packet inside a VPN tunnel.
    encapsulated: bool = False
    inner_summary: str | None = None

    # Device names in traversal order, appended as the frame moves.
    path: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
