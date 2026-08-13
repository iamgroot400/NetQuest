"""MAC address helpers.

Addresses are generated deterministically from the device and interface index
so that a saved topology always reloads with the same hardware addresses. That
makes packet traces reproducible, which matters for both teaching and tests.
"""

from __future__ import annotations

BROADCAST_MAC = "FF:FF:FF:FF:FF:FF"

# Locally administered, unicast OUI. Safe to invent addresses under it.
_OUI = (0x02, 0x00, 0x5E)

_HEX_DIGITS = set("0123456789ABCDEFabcdef")


def is_valid_mac(mac: str | None) -> bool:
    if not mac or not isinstance(mac, str):
        return False
    parts = mac.replace("-", ":").split(":")
    if len(parts) != 6:
        return False
    return all(len(p) == 2 and p[0] in _HEX_DIGITS and p[1] in _HEX_DIGITS for p in parts)


def normalize_mac(mac: str) -> str:
    return ":".join(p.upper() for p in mac.replace("-", ":").split(":"))


def is_broadcast_mac(mac: str) -> bool:
    return normalize_mac(mac) == BROADCAST_MAC


def generate_mac(device_index: int, interface_index: int = 0) -> str:
    """Build a stable MAC from a device/interface position.

    24 bits of address space is plenty: device index gets 16 bits and the
    interface index gets 8, so a device may carry up to 256 interfaces.
    """
    if not 0 <= device_index <= 0xFFFF:
        raise ValueError(f"device_index out of range: {device_index}")
    if not 0 <= interface_index <= 0xFF:
        raise ValueError(f"interface_index out of range: {interface_index}")
    tail = (
        (device_index >> 8) & 0xFF,
        device_index & 0xFF,
        interface_index & 0xFF,
    )
    return ":".join(f"{b:02X}" for b in (*_OUI, *tail))
