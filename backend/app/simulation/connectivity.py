"""Connection testing, shared by the `connect` command and the API endpoint.

The outcome distinctions here are the whole point of the exercise:

* **open** — something answered, so the service is listening and reachable.
* **refused** — the host answered with RST. It is up; nothing is on that port.
* **filtered** — nothing came back at all. Something in the middle swallowed it,
  which is what a firewall drop looks like from the outside.
* **unreachable** — a router said so explicitly.
* **no-route** — the packet never left the source.
* **dns-failure** — the name could not be turned into an address.

Telling *refused* from *filtered* is the single most useful diagnostic skill this
simulator can teach, so it is modelled honestly rather than collapsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .core.addressing import is_valid_ipv4
from .core.events import EventType, Severity, SimEvent
from .icmp.message import IcmpCode, IcmpMessage
from .transport.segment import (
    TcpFlag,
    TransportProtocol,
    TransportSegment,
    next_ephemeral_port,
)
from .transport.services import describe_port

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .core.engine import SimulationEngine
    from .devices.host import Host


class Outcome:
    OPEN = "open"
    REFUSED = "refused"
    FILTERED = "filtered"
    UNREACHABLE = "unreachable"
    NO_ROUTE = "no-route"
    DNS_FAILURE = "dns-failure"
    NO_SOURCE_ADDRESS = "no-source-address"


#: Events that mean "traffic stopped here", most specific first.
_STOP_EVENTS = (
    EventType.FIREWALL_DENY,
    EventType.PORT_CLOSED,
    EventType.ROUTE_MISS,
    EventType.TTL_EXPIRED,
    EventType.ARP_FAILED,
    EventType.NAT_NO_ENTRY,
    EventType.PACKET_DROPPED,
    EventType.FRAME_DROPPED,
)


@dataclass
class ConnectionAttempt:
    reachable: bool
    outcome: str
    detail: str
    target: str
    resolved_ip: str | None = None
    port: int | None = None
    protocol: str = "TCP"
    #: Device names the traffic actually crossed, in order.
    path: list[str] = field(default_factory=list)
    blocked_at: str | None = None
    blocked_reason: str | None = None
    dns_detail: str | None = None

    def summary(self) -> str:
        where = f" at {self.blocked_at}" if self.blocked_at else ""
        return f"{self.outcome}{where}: {self.detail}"


def attempt_connection(
    host: "Host",
    target: str,
    port: int,
    engine: "SimulationEngine",
    protocol: TransportProtocol = TransportProtocol.TCP,
) -> ConnectionAttempt:
    """Open one connection and report exactly what came back."""
    label = describe_port(protocol, port)

    if not host.ip_interfaces:
        return ConnectionAttempt(
            reachable=False,
            outcome=Outcome.NO_SOURCE_ADDRESS,
            detail=f"{host.name} has no IPv4 address, so it cannot open a connection",
            target=target,
            port=port,
            protocol=protocol.value,
        )

    address, dns_response = host.resolve_target(target, engine)
    if address is None:
        detail = (
            f"could not resolve {target}"
            if dns_response is None
            else f"DNS answered {dns_response.status.value} for {target}"
        )
        return ConnectionAttempt(
            reachable=False,
            outcome=Outcome.DNS_FAILURE,
            detail=detail,
            target=target,
            port=port,
            protocol=protocol.value,
            dns_detail=(dns_response.detail if dns_response else None),
        )

    mark = len(engine.events)
    host.transport_inbox.clear()
    host.icmp_inbox.clear()

    if protocol is TransportProtocol.TCP:
        segment = TransportSegment(
            protocol=TransportProtocol.TCP,
            src_port=next_ephemeral_port(),
            dst_port=port,
            flag=TcpFlag.SYN,
        )
        engine.log(
            EventType.TCP_SYN,
            f"{host.name}: opening a TCP connection to {address} on {label}",
            device=host,
        )
    else:
        segment = TransportSegment(
            protocol=TransportProtocol.UDP,
            src_port=next_ephemeral_port(),
            dst_port=port,
        )
        engine.log(
            EventType.UDP_DATAGRAM,
            f"{host.name}: sending a UDP probe to {address} on {label}",
            device=host,
        )

    emissions = host.send_segment(address, segment, engine)
    if not emissions:
        events = engine.events[mark:]
        stop = _last_stop(events)
        return ConnectionAttempt(
            reachable=False,
            outcome=Outcome.NO_ROUTE,
            detail=f"the packet never left {host.name}",
            target=target,
            resolved_ip=address,
            port=port,
            protocol=protocol.value,
            blocked_at=stop.device_name if stop else host.name,
            blocked_reason=stop.message if stop else None,
        )

    # Follow just this conversation, so ARP traffic stays out of the path.
    flow_id = getattr(emissions[0].frame, "flow_id", None)
    target_device_id = _device_id_holding(engine, address)

    engine.run(host, emissions)
    events = engine.events[mark:]
    path = _forward_path(events, engine, flow_id, target_device_id)

    # An explicit answer beats any inference.
    for _packet, seg in host.transport_inbox:
        if seg.flag is TcpFlag.SYN_ACK and seg.src_port == port:
            return ConnectionAttempt(
                reachable=True,
                outcome=Outcome.OPEN,
                detail=f"{address} accepted the connection on {label}",
                target=target,
                resolved_ip=address,
                port=port,
                protocol=protocol.value,
                path=path,
            )
        if seg.flag is TcpFlag.RST and seg.src_port == port:
            return ConnectionAttempt(
                reachable=False,
                outcome=Outcome.REFUSED,
                detail=(
                    f"{address} is up but refused the connection — "
                    f"nothing is listening on {label}"
                ),
                target=target,
                resolved_ip=address,
                port=port,
                protocol=protocol.value,
                path=path,
                blocked_at=_device_holding(engine, address),
            )

    if protocol is TransportProtocol.UDP:
        for _packet, seg in host.transport_inbox:
            if seg.protocol is TransportProtocol.UDP:
                return ConnectionAttempt(
                    reachable=True,
                    outcome=Outcome.OPEN,
                    detail=f"{address} answered on {label}",
                    target=target,
                    resolved_ip=address,
                    port=port,
                    protocol=protocol.value,
                    path=path,
                )

    for packet, icmp in host.icmp_inbox:
        if isinstance(icmp, IcmpMessage) and icmp.is_error:
            refused = icmp.code is IcmpCode.PORT_UNREACHABLE
            return ConnectionAttempt(
                reachable=False,
                outcome=Outcome.REFUSED if refused else Outcome.UNREACHABLE,
                detail=f"{packet.src_ip} replied {icmp.summary()}",
                target=target,
                resolved_ip=address,
                port=port,
                protocol=protocol.value,
                path=path,
                blocked_at=_device_holding(engine, packet.src_ip),
                blocked_reason=icmp.summary(),
            )

    stop = _last_stop(events)
    return ConnectionAttempt(
        reachable=False,
        outcome=Outcome.FILTERED,
        detail=(
            f"nothing came back from {address} on {label} — the traffic was "
            "dropped in transit rather than refused"
        ),
        target=target,
        resolved_ip=address,
        port=port,
        protocol=protocol.value,
        path=path,
        blocked_at=stop.device_name if stop else None,
        blocked_reason=stop.message if stop else None,
    )


# -- reading the trace ----------------------------------------------------


def _forward_path(
    events: list[SimEvent],
    engine: "SimulationEngine",
    flow_id: str | None,
    target_device_id: str | None,
) -> list[str]:
    """Devices the outbound packet crossed, in order, once each.

    Restricted to one flow so the ARP exchanges that made it possible do not
    appear, and truncated the moment the destination is reached so the reply
    journey is not tacked on the end.
    """
    path: list[str] = []

    def append(name: str | None) -> None:
        if name and (not path or path[-1] != name):
            path.append(name)

    for event in events:
        if event.type is not EventType.FRAME_TRANSMITTED:
            continue
        if flow_id is not None and event.flow_id != flow_id:
            continue

        append(event.device_name)
        if target_device_id and event.to_device_id == target_device_id:
            append(_name_of(engine, target_device_id))
            return path

    # It never arrived: show how far it actually got.
    last = next(
        (
            e
            for e in reversed(events)
            if e.type is EventType.FRAME_TRANSMITTED
            and (flow_id is None or e.flow_id == flow_id)
        ),
        None,
    )
    if last is not None and last.to_device_id:
        append(_name_of(engine, last.to_device_id))
    return path


def _last_stop(events: list[SimEvent]) -> SimEvent | None:
    """The most telling "it stopped here" event in the trace."""
    for wanted in _STOP_EVENTS:
        matches = [e for e in events if e.type is wanted]
        if matches:
            return matches[-1]
    errors = [e for e in events if e.severity is Severity.ERROR]
    return errors[-1] if errors else None


def _name_of(engine: "SimulationEngine", device_id: str) -> str | None:
    device = engine.network.device(device_id)
    return device.name if device else None


def _device_holding(engine: "SimulationEngine", ip: str) -> str | None:
    """The device that actually owns this address, or None."""
    if not is_valid_ipv4(ip):
        return None
    owners = engine.network.devices_with_ip(ip)
    return owners[0].name if owners else None


def _device_id_holding(engine: "SimulationEngine", ip: str) -> str | None:
    if not is_valid_ipv4(ip):
        return None
    owners = engine.network.devices_with_ip(ip)
    return owners[0].id if owners else None
