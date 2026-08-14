"""Decide whether a topology satisfies a challenge's objectives.

Connectivity objectives run the real simulation engine. There is no shortcut
that marks a ping objective complete because the wiring "looks right".
"""

from __future__ import annotations

from ..schemas.challenge import (
    ChallengeSchema,
    ChallengeValidationResponse,
    ObjectiveResult,
    ObjectiveSchema,
    ObjectiveType,
)
from ..schemas.topology import DeviceSchema, TopologySchema
from ..simulation.core.addressing import (
    is_valid_ipv4,
    is_valid_netmask,
    same_subnet,
)
from ..simulation.runner import run_command, run_connection_test


def validate(challenge: ChallengeSchema, topology: TopologySchema) -> ChallengeValidationResponse:
    results = [
        _check(objective, index, topology)
        for index, objective in enumerate(challenge.objectives)
    ]
    complete = bool(results) and all(r.complete for r in results)
    return ChallengeValidationResponse(
        challenge_id=challenge.id,
        complete=complete,
        objectives=results,
        xp=challenge.xp if complete else 0,
    )


def _check(objective: ObjectiveSchema, index: int, topology: TopologySchema) -> ObjectiveResult:
    handler = _HANDLERS.get(objective.type)
    if handler is None:  # pragma: no cover - guarded by the schema enum
        return _result(objective, index, False, "Unknown objective type.")
    complete, detail = handler(objective, topology)
    return _result(objective, index, complete, detail)


# -- individual objective types -----------------------------------------


def _device_exists(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    wanted = objective.count or 1
    if objective.device_type is not None:
        matches = [d for d in topology.devices if d.type == objective.device_type]
        label = f"{objective.device_type.value} devices"
    elif objective.device:
        matches = [d for d in topology.devices if d.name.lower() == objective.device.lower()]
        label = objective.device
    else:
        matches = list(topology.devices)
        label = "devices"

    found = len(matches)
    if found >= wanted:
        return True, f"Found {found} {label}."
    return False, f"Found {found} of {wanted} {label}."


def _link_exists(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    a = _device_by_name(topology, objective.a)
    b = _device_by_name(topology, objective.b)
    if a is None or b is None:
        missing = objective.a if a is None else objective.b
        return False, f"{missing} is not on the canvas yet."

    a_ifaces = {i.id for i in a.interfaces}
    b_ifaces = {i.id for i in b.interfaces}
    for link in topology.links:
        ends = {link.a.interface_id, link.b.interface_id}
        if ends & a_ifaces and ends & b_ifaces:
            if link.status != "up":
                return False, f"The cable between {a.name} and {b.name} is disconnected."
            return True, f"{a.name} is cabled to {b.name}."
    return False, f"No cable between {a.name} and {b.name}."


def _interface_configured(
    objective: ObjectiveSchema, topology: TopologySchema
) -> tuple[bool, str]:
    device = _device_by_name(topology, objective.device)
    if device is None:
        return False, f"{objective.device} is not on the canvas yet."

    # The default gateway is a device-level setting, not a per-interface one.
    if objective.gateway and device.config.gateway != objective.gateway:
        return False, (
            f"{device.name}'s default gateway is "
            f"{device.config.gateway or 'not set'}, expected {objective.gateway}."
        )

    if objective.interface:
        candidates = [
            i for i in device.interfaces if i.name.lower() == objective.interface.lower()
        ]
        if not candidates:
            return False, f"{device.name} has no interface called {objective.interface}."
    else:
        candidates = list(device.interfaces)

    problems: list[str] = []
    for iface in candidates:
        matched, problem = _interface_matches(iface, objective)
        if matched:
            return True, f"{device.name} {iface.name} is configured."
        problems.append(problem)

    return False, f"{device.name}: " + "; ".join(problems or ["no interfaces to check"]) + "."


def _interface_matches(iface, objective: ObjectiveSchema) -> tuple[bool, str]:
    """An objective may pin exact values, or just require *something* valid."""
    if objective.ipv4:
        if iface.ipv4 != objective.ipv4:
            return False, f"{iface.name} address is {iface.ipv4 or 'unset'}"
    elif not is_valid_ipv4(iface.ipv4):
        return False, f"{iface.name} has no valid IP address"

    if objective.netmask:
        if iface.netmask != objective.netmask:
            return False, f"{iface.name} mask is {iface.netmask or 'unset'}"
    elif not is_valid_netmask(iface.netmask):
        return False, f"{iface.name} has no valid subnet mask"

    return True, ""


def _in_subnet(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    device = _device_by_name(topology, objective.device)
    if device is None:
        return False, f"{objective.device} is not on the canvas yet."
    if not (objective.subnet and is_valid_ipv4(objective.subnet)):
        return False, "The challenge does not specify a valid subnet."
    mask = objective.netmask or "255.255.255.0"

    for iface in device.interfaces:
        if not (is_valid_ipv4(iface.ipv4) and is_valid_netmask(iface.netmask)):
            continue
        assert iface.ipv4
        if same_subnet(iface.ipv4, objective.subnet, mask):
            return True, f"{device.name} {iface.name} is inside {objective.subnet}."
    return False, f"No interface on {device.name} is inside {objective.subnet} / {mask}."


def _ping(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    source = _device_by_name(topology, objective.source)
    if source is None:
        return False, f"{objective.source} is not on the canvas yet."

    target = _resolve_target(topology, objective.destination)
    if target is None:
        return False, f"{objective.destination} has no IP address to ping."

    result = run_command(topology, source.id, f"ping {target} -n 1")
    reached = result.success
    want_success = objective.type is ObjectiveType.PING_SUCCEEDS

    if reached == want_success:
        detail = (
            f"{source.name} can reach {target}."
            if want_success
            else f"{source.name} correctly cannot reach {target}."
        )
    else:
        detail = (
            f"{source.name} cannot reach {target} yet."
            if want_success
            else f"{source.name} can still reach {target}."
        )
    return reached == want_success, detail


def _dns_resolves(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    device = _device_by_name(topology, objective.device)
    if device is None:
        return False, f"{objective.device} is not on the canvas yet."
    if not objective.name:
        return False, "The challenge does not say which name to resolve."

    result = run_command(topology, device.id, f"nslookup {objective.name}")
    if not result.success:
        detail = next(
            (line for line in result.output if "can't find" in line or "no response" in line),
            f"{device.name} could not resolve {objective.name}.",
        )
        return False, detail.strip()

    address = next(
        (line.split(":", 1)[1].strip() for line in result.output if line.startswith("Address:")),
        None,
    )
    # The first "Address:" line is the server; the last is the answer.
    answers = [
        line.split(":", 1)[1].strip()
        for line in result.output
        if line.startswith("Address:")
    ]
    address = answers[-1] if answers else address

    if objective.expects and address != objective.expects:
        return False, (
            f"{objective.name} resolves to {address}, but it should be {objective.expects}."
        )
    return True, f"{objective.name} resolves to {address}."


def _service_check(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    source = _device_by_name(topology, objective.source)
    if source is None:
        return False, f"{objective.source} is not on the canvas yet."
    if objective.port is None:
        return False, "The challenge does not say which port to test."

    destination = objective.destination or ""
    result = run_connection_test(
        topology, source.id, destination, objective.port, objective.protocol
    )
    want_reachable = objective.type is ObjectiveType.SERVICE_REACHABLE

    label = f"{destination} on {objective.port}/{objective.protocol.lower()}"
    if result.reachable == want_reachable:
        detail = (
            f"{source.name} can reach {label}."
            if want_reachable
            else f"{source.name} correctly cannot reach {label} ({result.outcome})."
        )
        return True, detail

    if want_reachable:
        where = f" — stopped at {result.blocked_at}" if result.blocked_at else ""
        return False, f"{source.name} cannot reach {label}: {result.outcome}{where}."
    return False, f"{source.name} can still reach {label}."


def _service_enabled(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    device = _device_by_name(topology, objective.device)
    if device is None:
        return False, f"{objective.device} is not on the canvas yet."
    if objective.port is None:
        return False, "The challenge does not say which port to check."

    wanted = objective.protocol.upper()
    listening = [
        s
        for s in device.config.services
        if s.enabled and s.port == objective.port and s.protocol.upper() == wanted
    ]
    if listening:
        return True, f"{device.name} is listening on {objective.port}/{wanted.lower()}."
    return False, (
        f"{device.name} is not listening on {objective.port}/{wanted.lower()}."
    )


def _dhcp_assigns(objective: ObjectiveSchema, topology: TopologySchema) -> tuple[bool, str]:
    device = _device_by_name(topology, objective.device)
    if device is None:
        return False, f"{objective.device} is not on the canvas yet."
    if not device.config.dhcp_client:
        return False, f"{device.name} is not set to obtain its address automatically."

    addressed = [i for i in device.interfaces if is_valid_ipv4(i.ipv4)]
    if not addressed:
        return False, (
            f"{device.name} has no address yet — run 'dhcp renew' in its terminal."
        )

    iface = addressed[0]
    assert iface.ipv4
    if objective.subnet:
        mask = objective.netmask or iface.netmask or "255.255.255.0"
        if not same_subnet(iface.ipv4, objective.subnet, mask):
            return False, (
                f"{device.name} was given {iface.ipv4}, which is not inside "
                f"{objective.subnet}."
            )
    if objective.gateway and device.config.gateway != objective.gateway:
        return False, (
            f"{device.name} was given gateway "
            f"{device.config.gateway or 'none'}, expected {objective.gateway}."
        )
    return True, f"{device.name} holds {iface.ipv4} from DHCP."


_HANDLERS = {
    ObjectiveType.DEVICE_EXISTS: _device_exists,
    ObjectiveType.LINK_EXISTS: _link_exists,
    ObjectiveType.INTERFACE_CONFIGURED: _interface_configured,
    ObjectiveType.IN_SUBNET: _in_subnet,
    ObjectiveType.PING_SUCCEEDS: _ping,
    ObjectiveType.PING_FAILS: _ping,
    ObjectiveType.DNS_RESOLVES: _dns_resolves,
    ObjectiveType.SERVICE_REACHABLE: _service_check,
    ObjectiveType.SERVICE_BLOCKED: _service_check,
    ObjectiveType.SERVICE_ENABLED: _service_enabled,
    ObjectiveType.DHCP_ASSIGNS: _dhcp_assigns,
}


# -- helpers -------------------------------------------------------------


def _device_by_name(topology: TopologySchema, name: str | None) -> DeviceSchema | None:
    if not name:
        return None
    lowered = name.lower()
    for device in topology.devices:
        if device.name.lower() == lowered:
            return device
    return None


def _resolve_target(topology: TopologySchema, destination: str | None) -> str | None:
    """A ping destination may be a literal address or a device name."""
    if not destination:
        return None
    if is_valid_ipv4(destination):
        return destination
    device = _device_by_name(topology, destination)
    if device is None:
        return None
    for iface in device.interfaces:
        if iface.enabled and is_valid_ipv4(iface.ipv4):
            return iface.ipv4
    return None


def _result(
    objective: ObjectiveSchema, index: int, complete: bool, detail: str
) -> ObjectiveResult:
    return ObjectiveResult(
        index=index,
        type=objective.type,
        description=objective.description or describe(objective),
        complete=complete,
        detail=detail,
    )


def describe(objective: ObjectiveSchema) -> str:
    """Readable objective text, so challenge files can stay terse."""
    match objective.type:
        case ObjectiveType.DEVICE_EXISTS:
            count = objective.count or 1
            what = objective.device or (
                objective.device_type.value if objective.device_type else "device"
            )
            plural = "s" if count > 1 else ""
            return f"Add {count} {what}{plural} to the canvas"
        case ObjectiveType.LINK_EXISTS:
            return f"Connect {objective.a} to {objective.b}"
        case ObjectiveType.INTERFACE_CONFIGURED:
            bits = []
            if objective.ipv4:
                bits.append(f"IP {objective.ipv4}")
            if objective.netmask:
                bits.append(f"mask {objective.netmask}")
            if objective.gateway:
                bits.append(f"gateway {objective.gateway}")
            suffix = f" with {', '.join(bits)}" if bits else ""
            return f"Configure {objective.device}{suffix}"
        case ObjectiveType.IN_SUBNET:
            return f"Put {objective.device} inside the {objective.subnet} network"
        case ObjectiveType.PING_SUCCEEDS:
            return f"{objective.source} can ping {objective.destination}"
        case ObjectiveType.PING_FAILS:
            return f"{objective.source} cannot reach {objective.destination}"
        case ObjectiveType.DNS_RESOLVES:
            target = f" to {objective.expects}" if objective.expects else ""
            return f"{objective.device} can resolve {objective.name}{target}"
        case ObjectiveType.SERVICE_REACHABLE:
            return (
                f"{objective.source} can reach {objective.destination} on "
                f"{objective.port}/{objective.protocol.lower()}"
            )
        case ObjectiveType.SERVICE_BLOCKED:
            return (
                f"{objective.source} cannot reach {objective.destination} on "
                f"{objective.port}/{objective.protocol.lower()}"
            )
        case ObjectiveType.SERVICE_ENABLED:
            return (
                f"{objective.device} is listening on "
                f"{objective.port}/{objective.protocol.lower()}"
            )
        case ObjectiveType.DHCP_ASSIGNS:
            where = f" inside {objective.subnet}" if objective.subnet else ""
            return f"{objective.device} gets its address from DHCP{where}"
    return "Objective"  # pragma: no cover
