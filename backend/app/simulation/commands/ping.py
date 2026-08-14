"""The ping command.

Shared by hosts and routers. Nothing here decides whether a ping succeeds: it
builds an echo request, hands it to the engine, and then reports whatever
actually landed in the device's ICMP inbox. If no frame made it back, the
output says so.
"""

from __future__ import annotations

from ..core.addressing import is_valid_ipv4
from ..icmp.message import ECHO_PAYLOAD_BYTES, IcmpCode, IcmpMessage, IcmpType
from ..ipv4.packet import DEFAULT_TTL, IPProtocol, IPv4Packet
from .registry import CommandContext, CommandResult

DEFAULT_COUNT = 4
MAX_COUNT = 10

_ERROR_TEXT = {
    (IcmpType.DESTINATION_UNREACHABLE, IcmpCode.NET_UNREACHABLE): "Destination net unreachable.",
    (IcmpType.DESTINATION_UNREACHABLE, IcmpCode.HOST_UNREACHABLE): "Destination host unreachable.",
    (IcmpType.TIME_EXCEEDED, IcmpCode.TTL_EXCEEDED_IN_TRANSIT): "TTL expired in transit.",
}


def _parse_args(args: list[str]) -> tuple[str | None, int, str | None]:
    """Return (target, count, error)."""
    target: str | None = None
    count = DEFAULT_COUNT
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("-n", "-c"):
            if i + 1 >= len(args) or not args[i + 1].isdigit():
                return None, count, f"Value must be supplied for option {token}."
            count = max(1, min(MAX_COUNT, int(args[i + 1])))
            i += 2
            continue
        if target is None:
            target = token
        i += 1

    if target is None:
        return None, count, "Usage: ping <ip address> [-n count]"
    return target, count, None


def run_ping(ctx: CommandContext) -> CommandResult:
    device = ctx.device
    engine = ctx.engine

    target, count, error = _parse_args(ctx.args)
    if error:
        return CommandResult(output=[error], success=False)
    assert target

    if not device.ip_interfaces:
        return CommandResult(
            output=[
                "PING: transmit failed. General failure.",
                f"{device.name} has no IPv4 address configured on an enabled interface.",
            ],
            success=False,
        )

    # A name has to be resolved first, and a DNS failure is reported as such
    # rather than as a dead host — telling those apart is the point.
    address = target
    if not is_valid_ipv4(target):
        resolved, response = device.resolve_target(target, engine)
        if resolved is None:
            lines = [f"Ping request could not find host {target}."]
            if response is None:
                lines.append(
                    "No DNS server is configured on this host, or it did not answer."
                )
            else:
                lines.append(
                    f"DNS answered {response.status.value}"
                    + (f" — {response.detail}" if response.detail else "")
                )
            return CommandResult(output=lines, success=False)
        address = resolved

    shown = target if address == target else f"{target} [{address}]"

    if device.owns_ip(address):
        lines = [f"Pinging {shown} with {ECHO_PAYLOAD_BYTES} bytes of data:", ""]
        lines += [
            f"Reply from {address}: bytes={ECHO_PAYLOAD_BYTES} TTL={DEFAULT_TTL} (local interface)"
        ] * count
        lines += _statistics(address, count, count)
        return CommandResult(output=lines)

    target = address
    lines = [f"Pinging {shown} with {ECHO_PAYLOAD_BYTES} bytes of data:", ""]
    received = 0

    for sequence in range(1, count + 1):
        device.icmp_inbox.clear()

        source_ip = device.select_source_ip(target) or (
            device.ip_interfaces[0].ipv4 or ""
        )
        packet = IPv4Packet(
            src_ip=source_ip,
            dst_ip=target,
            protocol=IPProtocol.ICMP,
            payload=IcmpMessage(
                type=IcmpType.ECHO_REQUEST, identifier=1, sequence=sequence
            ),
            ttl=DEFAULT_TTL,
            length=ECHO_PAYLOAD_BYTES,
        )

        emissions = device.send_ipv4(packet, engine)
        if not emissions:
            # The packet never reached the wire: no route, or ARP found nobody.
            lines.append("Destination host unreachable.")
            continue

        engine.run(device, emissions)
        lines.append(_result_line(device, target, sequence))
        if _echo_reply(device, sequence) is not None:
            received += 1

    lines += _statistics(target, count, received)
    return CommandResult(output=lines, success=received > 0)


def _echo_reply(device, sequence: int):
    for packet, icmp in device.icmp_inbox:
        if icmp.type is IcmpType.ECHO_REPLY and icmp.sequence == sequence:
            return packet, icmp
    return None


def _result_line(device, target: str, sequence: int) -> str:
    reply = _echo_reply(device, sequence)
    if reply is not None:
        packet, _ = reply
        return (
            f"Reply from {packet.src_ip}: bytes={packet.length} TTL={packet.ttl}"
        )

    for packet, icmp in device.icmp_inbox:
        if icmp.is_error:
            text = _ERROR_TEXT.get((icmp.type, icmp.code), icmp.summary())
            return f"Reply from {packet.src_ip}: {text}"

    return "Request timed out."


def _statistics(target: str, sent: int, received: int) -> list[str]:
    lost = sent - received
    percent = round(lost / sent * 100) if sent else 0
    return [
        "",
        f"Ping statistics for {target}:",
        f"    Packets: Sent = {sent}, Received = {received}, "
        f"Lost = {lost} ({percent}% loss)",
    ]
