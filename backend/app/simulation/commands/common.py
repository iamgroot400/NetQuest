"""Output helpers shared by more than one device's command set."""

from __future__ import annotations

from ..core.addressing import netmask_to_prefix
from ..core.models import Interface
from ..core.network import Network


def line_protocol(network: Network, interface: Interface) -> tuple[str, str]:
    """Return (state, description) for an interface's physical connection.

    Mirrors how real gear reports it: the interface itself can be up while the
    line protocol is down because nothing is plugged in.
    """
    link = network.link_for(interface.id)
    if link is None:
        return "down", "no cable attached"
    if not link.is_up:
        return "down", "cable disconnected"
    peer = network.peer_of(interface.id)
    if peer is None:
        return "down", "cable is not connected at the far end"
    peer_device, peer_iface = peer
    if not peer_iface.enabled:
        return "down", f"{peer_device.name} {peer_iface.name} is administratively down"
    return "up", f"connected to {peer_device.name} {peer_iface.name}"


def show_interfaces(network: Network, device) -> list[str]:
    if not device.interfaces:
        return ["This device has no interfaces."]

    lines: list[str] = []
    for iface in device.interfaces:
        protocol, description = line_protocol(network, iface)
        admin = "up" if iface.enabled else "administratively down"
        lines.append(f"{iface.name} is {admin}, line protocol is {protocol}")
        lines.append(f"  Hardware address is {iface.mac}")
        if iface.has_ip and iface.netmask:
            lines.append(
                f"  Internet address is {iface.ipv4}/{netmask_to_prefix(iface.netmask)} "
                f"({iface.netmask})"
            )
        else:
            lines.append("  Internet address is not set")
        lines.append(f"  {description[0].upper()}{description[1:]}")
        lines.append("")
    return lines
