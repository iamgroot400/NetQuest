"""Transparent inline firewall.

Sits between two segments like a bridge and passes frames straight through,
except that IPv4 traffic is checked against an ordered rule list first. It needs
no addresses of its own, so it can be dropped into any topology exactly where
the diagram shows it.

Rules are evaluated top to bottom and the first match wins — which is why a
broad `deny` above a specific `allow` silently defeats it. The event log always
names the rule that decided, so that mistake is discoverable rather than
mysterious.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..core.addressing import ip_matches_cidr
from ..core.events import EventType, Severity
from ..core.models import DeviceConfig, Emission, FirewallRuleConfig, Interface
from ..ethernet.frame import EtherType, EthernetFrame
from ..icmp.message import IcmpMessage
from ..ipv4.packet import IPProtocol, IPv4Packet
from ..transport.segment import TransportSegment
from ..transport.services import describe_port
from .base import Device

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ..core.engine import SimulationEngine

ALLOW = "allow"
DENY = "deny"
ANY_PROTOCOL = "any"


@dataclass
class Verdict:
    allowed: bool
    rule_index: int | None
    rule: FirewallRuleConfig | None
    reason: str


class Firewall(Device):
    kind = "firewall"

    def __init__(
        self,
        id: str,
        name: str,
        interfaces: list[Interface],
        config: DeviceConfig | None = None,
    ) -> None:
        super().__init__(id, name, interfaces, config)
        #: Rule index (as a string, for JSON) -> how many packets it decided.
        self.hits: dict[str, int] = {}
        #: Reverse flow keys permitted because the outbound direction was.
        #:
        #: This makes the firewall *stateful*, like every firewall a learner
        #: will meet. A stateless one would need a matching rule for the reply
        #: of every allowed request, so `allow tcp 80` would block the very
        #: connection it was written to permit — a trap, not a lesson.
        self._established: set[tuple] = set()

    @property
    def rules(self) -> list[FirewallRuleConfig]:
        return self.config.firewall_rules

    @property
    def default_policy(self) -> str:
        return DENY if self.config.firewall_default_policy == DENY else ALLOW

    # -- rule evaluation --------------------------------------------------

    def evaluate(self, packet: IPv4Packet) -> Verdict:
        protocol = packet.protocol
        segment = packet.payload if isinstance(packet.payload, TransportSegment) else None
        dst_port = segment.dst_port if segment else None

        # Return traffic for a conversation we already let out is allowed
        # without re-consulting the rules.
        forward_key = _flow_key(packet)
        if forward_key is not None and forward_key in self._established:
            return Verdict(
                allowed=True,
                rule_index=None,
                rule=None,
                reason="established connection",
            )

        for index, rule in enumerate(self.rules):
            if not self._matches(rule, protocol, dst_port, packet):
                continue
            allowed = rule.action != DENY
            return Verdict(
                allowed=allowed,
                rule_index=index,
                rule=rule,
                reason=self._describe(rule, index),
            )

        return Verdict(
            allowed=self.default_policy == ALLOW,
            rule_index=None,
            rule=None,
            reason=f"no rule matched, default policy is {self.default_policy}",
        )

    def _matches(
        self,
        rule: FirewallRuleConfig,
        protocol: IPProtocol,
        dst_port: int | None,
        packet: IPv4Packet,
    ) -> bool:
        wanted = (rule.protocol or ANY_PROTOCOL).strip().lower()
        if wanted != ANY_PROTOCOL and wanted != protocol.value.lower():
            return False

        # A port only means anything for TCP and UDP.
        if rule.port is not None:
            if protocol not in (IPProtocol.TCP, IPProtocol.UDP):
                return False
            if dst_port != rule.port:
                return False

        if not ip_matches_cidr(packet.src_ip, rule.source):
            return False
        if not ip_matches_cidr(packet.dst_ip, rule.destination):
            return False
        return True

    def _describe(self, rule: FirewallRuleConfig, index: int) -> str:
        parts = [f"rule {index + 1}", rule.action]
        protocol = (rule.protocol or ANY_PROTOCOL).lower()
        if rule.port is not None and protocol in ("tcp", "udp"):
            from ..transport.segment import TransportProtocol

            parts.append(
                describe_port(
                    TransportProtocol.TCP if protocol == "tcp" else TransportProtocol.UDP,
                    rule.port,
                )
            )
        else:
            parts.append(protocol)
        if (rule.source or "any").lower() != "any":
            parts.append(f"from {rule.source}")
        if (rule.destination or "any").lower() != "any":
            parts.append(f"to {rule.destination}")
        if rule.description:
            parts.append(f"({rule.description})")
        return " ".join(parts)

    # -- forwarding -------------------------------------------------------

    def receive_frame(
        self,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        if frame.ethertype is EtherType.IPV4 and isinstance(frame.payload, IPv4Packet):
            packet = frame.payload
            verdict = self.evaluate(packet)
            if verdict.reason != "established connection":
                key = "default" if verdict.rule_index is None else str(verdict.rule_index)
                self.hits[key] = self.hits.get(key, 0) + 1

            if verdict.allowed:
                # Remember the reverse direction so the reply gets through.
                reverse = _flow_key(packet, reverse=True)
                if reverse is not None:
                    self._established.add(reverse)

            if not verdict.allowed:
                engine.log(
                    EventType.FIREWALL_DENY,
                    f"{self.name}: blocked {_describe_traffic(packet)} — {verdict.reason}",
                    severity=Severity.ERROR,
                    device=self,
                    interface=in_interface,
                    frame=frame,
                )
                return []

            engine.log(
                EventType.FIREWALL_ALLOW,
                f"{self.name}: permitted {_describe_traffic(packet)} — {verdict.reason}",
                device=self,
                interface=in_interface,
                frame=frame,
            )

        return self._forward(frame, in_interface, engine)

    def _forward(
        self,
        frame: EthernetFrame,
        in_interface: Interface,
        engine: "SimulationEngine",
    ) -> list[Emission]:
        """Pass the frame out of every other live port, unchanged.

        ARP is never filtered: without it nothing on either side could resolve
        a MAC address and the firewall would look like a cut cable.
        """
        targets = [
            iface
            for iface in self.enabled_interfaces
            if iface.id != in_interface.id and self._port_is_live(iface, engine)
        ]
        if not targets:
            engine.log(
                EventType.FRAME_DROPPED,
                f"{self.name}: nothing on the other side to forward to — frame dropped",
                severity=Severity.WARNING,
                device=self,
                interface=in_interface,
                frame=frame,
            )
            return []
        return [Emission(interface_id=iface.id, frame=frame) for iface in targets]

    @staticmethod
    def _port_is_live(interface: Interface, engine: "SimulationEngine") -> bool:
        link = engine.network.link_for(interface.id)
        return link is not None and link.is_up

    # -- runtime state ----------------------------------------------------

    def state(self) -> dict[str, Any]:
        return {
            "arp_table": {},
            "mac_table": {},
            "firewall_hits": dict(self.hits),
        }

    def load_state(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        self.hits = {k: int(v) for k, v in (state.get("firewall_hits") or {}).items()}


def _flow_key(packet: IPv4Packet, reverse: bool = False) -> tuple | None:
    """Identify one conversation, optionally in the opposite direction.

    ICMP echoes carry an identifier that is copied into the reply, so the same
    key works both ways round for them.
    """
    payload = packet.payload
    if isinstance(payload, TransportSegment):
        if reverse:
            return (
                packet.protocol.value,
                packet.dst_ip,
                payload.dst_port,
                packet.src_ip,
                payload.src_port,
            )
        return (
            packet.protocol.value,
            packet.src_ip,
            payload.src_port,
            packet.dst_ip,
            payload.dst_port,
        )

    if isinstance(payload, IcmpMessage):
        if reverse:
            return ("ICMP", packet.dst_ip, packet.src_ip, payload.identifier)
        return ("ICMP", packet.src_ip, packet.dst_ip, payload.identifier)

    return None


def _describe_traffic(packet: IPv4Packet) -> str:
    segment = packet.payload if isinstance(packet.payload, TransportSegment) else None
    if segment is not None:
        return (
            f"{packet.src_ip} → {packet.dst_ip} "
            f"{describe_port(segment.protocol, segment.dst_port)}"
        )
    return f"{packet.protocol.value} {packet.src_ip} → {packet.dst_ip}"
