"""Static checks on a topology.

These are configuration mistakes that can be spotted without sending a single
frame. They are surfaced as hints in the UI — never auto-corrected, because
finding them is the point of the troubleshooting missions.
"""

from __future__ import annotations

from collections import defaultdict

from ..schemas.simulation import ValidationIssue, ValidationResponse
from ..schemas.topology import DeviceType, TopologySchema
from .core.addressing import (
    broadcast_address,
    is_usable_host_ip,
    is_valid_ipv4,
    is_valid_netmask,
    network_address,
    same_subnet,
)

ERROR = "error"
WARNING = "warning"

#: Layer 2 devices have no IP stack in the MVP, so address checks skip them.
L3_TYPES = {DeviceType.PC, DeviceType.ROUTER, DeviceType.SERVER}


def validate_topology(topology: TopologySchema) -> ValidationResponse:
    issues: list[ValidationIssue] = []
    ip_owners: dict[str, list[str]] = defaultdict(list)
    interfaces_in_use: dict[str, int] = defaultdict(int)

    for link in topology.links:
        interfaces_in_use[link.a.interface_id] += 1
        interfaces_in_use[link.b.interface_id] += 1

    for device in topology.devices:
        if device.type not in L3_TYPES:
            continue

        for iface in device.interfaces:
            has_ip = bool(iface.ipv4)
            has_mask = bool(iface.netmask)

            if has_ip and not is_valid_ipv4(iface.ipv4):
                issues.append(
                    _issue(
                        ERROR, device, iface.id,
                        f"{iface.name}: '{iface.ipv4}' is not a valid IPv4 address.",
                    )
                )
                continue

            if has_mask and not is_valid_netmask(iface.netmask):
                issues.append(
                    _issue(
                        ERROR, device, iface.id,
                        f"{iface.name}: '{iface.netmask}' is not a valid subnet mask. "
                        "A mask must be a solid run of ones, like 255.255.255.0.",
                    )
                )
                continue

            if has_ip and not has_mask:
                issues.append(
                    _issue(
                        ERROR, device, iface.id,
                        f"{iface.name} has an IP address but no subnet mask, "
                        "so it cannot tell which hosts are local.",
                    )
                )
                continue

            if not has_ip:
                if iface.enabled and interfaces_in_use.get(iface.id):
                    issues.append(
                        _issue(
                            WARNING, device, iface.id,
                            f"{iface.name} is cabled but has no IP address.",
                        )
                    )
                continue

            assert iface.ipv4 and iface.netmask
            ip_owners[iface.ipv4].append(f"{device.name} ({iface.name})")

            if not is_usable_host_ip(iface.ipv4, iface.netmask):
                kind = (
                    "network address"
                    if iface.ipv4 == network_address(iface.ipv4, iface.netmask)
                    else "broadcast address"
                )
                issues.append(
                    _issue(
                        ERROR, device, iface.id,
                        f"{iface.name}: {iface.ipv4} is the {kind} of its subnet "
                        "and cannot be assigned to a host.",
                    )
                )

        _check_gateway(device, issues)

    for ip, owners in ip_owners.items():
        if len(owners) > 1:
            issues.append(
                ValidationIssue(
                    severity=ERROR,
                    message=f"Duplicate IP address {ip} is configured on: {', '.join(owners)}.",
                )
            )

    for interface_id, count in interfaces_in_use.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    severity=ERROR,
                    interface_id=interface_id,
                    message="An interface has more than one cable attached to it.",
                )
            )

    return ValidationResponse(
        valid=not any(i.severity == ERROR for i in issues), issues=issues
    )


def _check_gateway(device, issues: list[ValidationIssue]) -> None:
    gateway = device.config.gateway
    if not gateway:
        return

    if not is_valid_ipv4(gateway):
        issues.append(
            _issue(ERROR, device, None, f"Default gateway '{gateway}' is not a valid IPv4 address.")
        )
        return

    usable = [
        i
        for i in device.interfaces
        if i.enabled and is_valid_ipv4(i.ipv4) and is_valid_netmask(i.netmask)
    ]
    if not usable:
        return

    for iface in usable:
        assert iface.ipv4 and iface.netmask
        if same_subnet(iface.ipv4, gateway, iface.netmask):
            if gateway == iface.ipv4:
                issues.append(
                    _issue(
                        WARNING, device, iface.id,
                        f"The default gateway {gateway} is this device's own address.",
                    )
                )
            elif gateway == broadcast_address(iface.ipv4, iface.netmask):
                issues.append(
                    _issue(
                        ERROR, device, iface.id,
                        f"The default gateway {gateway} is the subnet's broadcast address.",
                    )
                )
            return

    first = usable[0]
    assert first.ipv4 and first.netmask
    issues.append(
        _issue(
            ERROR, device, first.id,
            f"Default gateway {gateway} is not inside "
            f"{network_address(first.ipv4, first.netmask)} "
            f"mask {first.netmask}, so this device can never reach it.",
        )
    )


def _issue(severity: str, device, interface_id: str | None, message: str) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        device_id=device.id,
        device_name=device.name,
        interface_id=interface_id,
        message=message,
    )
