"""IPv4 addressing helpers.

The engine speaks dotted-quad strings everywhere, because that is exactly what
the device CLIs and the configuration UI show. All conversion to and from
integers is confined to this module so the rest of the engine never has to
think about bit twiddling.
"""

from __future__ import annotations

ANY_IPV4 = "0.0.0.0"
LIMITED_BROADCAST = "255.255.255.255"
DEFAULT_NETMASK = "255.255.255.0"

# Netmasks are contiguous runs of ones, so only 33 values are legal.
_VALID_MASK_INTS = {((0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF) for p in range(33)}


def is_valid_ipv4(value: str | None) -> bool:
    """True for a well-formed dotted-quad address."""
    if not value or not isinstance(value, str):
        return False
    parts = value.strip().split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part[0] == "0"):
            return False
        if not 0 <= int(part) <= 255:
            return False
    return True


def ip_to_int(ip: str) -> int:
    a, b, c, d = (int(p) for p in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(value: int) -> str:
    value &= 0xFFFFFFFF
    return f"{(value >> 24) & 0xFF}.{(value >> 16) & 0xFF}.{(value >> 8) & 0xFF}.{value & 0xFF}"


def is_valid_netmask(mask: str | None) -> bool:
    """A netmask must be a valid address *and* a contiguous run of ones."""
    if not is_valid_ipv4(mask):
        return False
    return ip_to_int(mask) in _VALID_MASK_INTS  # type: ignore[arg-type]


def netmask_to_prefix(mask: str) -> int:
    return bin(ip_to_int(mask)).count("1")


def prefix_to_netmask(prefix: int) -> str:
    if not 0 <= prefix <= 32:
        raise ValueError(f"prefix out of range: {prefix}")
    return int_to_ip((0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix else 0)


def network_address(ip: str, mask: str) -> str:
    return int_to_ip(ip_to_int(ip) & ip_to_int(mask))


def broadcast_address(ip: str, mask: str) -> str:
    return int_to_ip(ip_to_int(ip) | (~ip_to_int(mask) & 0xFFFFFFFF))


def same_subnet(a: str, b: str, mask: str) -> bool:
    """Would a host with address `a`/`mask` consider `b` directly reachable?"""
    return ip_to_int(a) & ip_to_int(mask) == ip_to_int(b) & ip_to_int(mask)


def ip_in_network(ip: str, network: str, mask: str) -> bool:
    return ip_to_int(ip) & ip_to_int(mask) == ip_to_int(network) & ip_to_int(mask)


def is_broadcast_ip(ip: str, local_ip: str | None = None, mask: str | None = None) -> bool:
    """True for the limited broadcast, or the directed broadcast of a local subnet."""
    if ip == LIMITED_BROADCAST:
        return True
    if local_ip and mask and is_valid_ipv4(local_ip) and is_valid_netmask(mask):
        return ip == broadcast_address(local_ip, mask)
    return False


def is_usable_host_ip(ip: str, mask: str) -> bool:
    """Reject the network and broadcast addresses of the subnet.

    Only meaningful for prefixes shorter than /31, where those addresses are
    reserved. /31 and /32 have no reserved addresses.
    """
    if netmask_to_prefix(mask) >= 31:
        return True
    return ip not in (network_address(ip, mask), broadcast_address(ip, mask))


def format_cidr(ip: str, mask: str) -> str:
    return f"{ip}/{netmask_to_prefix(mask)}"


#: Firewall rules and NAT scopes are written as CIDR, or the word "any".
ANY_CIDR = "any"


def parse_cidr(value: str) -> tuple[str, str] | None:
    """Split "192.168.1.0/24" into (network, netmask), or None if malformed.

    A bare address is treated as a /32 host route, which is what a firewall
    rule naming a single machine means.
    """
    text = (value or "").strip()
    if not text or text.lower() == ANY_CIDR:
        return None

    if "/" not in text:
        return (text, "255.255.255.255") if is_valid_ipv4(text) else None

    address, _, prefix_text = text.partition("/")
    if not is_valid_ipv4(address) or not prefix_text.isdigit():
        return None
    prefix = int(prefix_text)
    if not 0 <= prefix <= 32:
        return None
    return address, prefix_to_netmask(prefix)


def ip_matches_cidr(ip: str, value: str) -> bool:
    """True when `ip` falls inside `value`. The word "any" matches everything."""
    if not (value or "").strip() or value.strip().lower() == ANY_CIDR:
        return True
    parsed = parse_cidr(value)
    if parsed is None:
        # An unparseable scope must never silently match everything.
        return False
    network, mask = parsed
    return is_valid_ipv4(ip) and ip_in_network(ip, network, mask)


def ip_between(ip: str, first: str, last: str) -> bool:
    """Inclusive range test, used for DHCP pools."""
    if not (is_valid_ipv4(ip) and is_valid_ipv4(first) and is_valid_ipv4(last)):
        return False
    return ip_to_int(first) <= ip_to_int(ip) <= ip_to_int(last)


def iter_range(first: str, last: str, limit: int = 4096):
    """Addresses from `first` to `last` inclusive, capped to stay bounded."""
    if not (is_valid_ipv4(first) and is_valid_ipv4(last)):
        return
    start, end = ip_to_int(first), ip_to_int(last)
    if end < start:
        return
    for offset in range(min(end - start + 1, limit)):
        yield int_to_ip(start + offset)
