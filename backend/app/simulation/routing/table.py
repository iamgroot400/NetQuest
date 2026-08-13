"""IPv4 routing table with longest-prefix matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..core.addressing import (
    ANY_IPV4,
    ip_in_network,
    netmask_to_prefix,
    network_address,
)


class RouteKind(str, Enum):
    CONNECTED = "connected"
    STATIC = "static"
    DEFAULT = "default"


@dataclass
class Route:
    destination: str
    netmask: str
    interface_id: str
    # None means the destination is directly attached; otherwise the next-hop router.
    gateway: str | None = None
    kind: RouteKind = RouteKind.STATIC
    metric: int = 0

    @property
    def prefix_length(self) -> int:
        return netmask_to_prefix(self.netmask)

    @property
    def is_default(self) -> bool:
        return self.destination == ANY_IPV4 and self.prefix_length == 0

    def matches(self, ip: str) -> bool:
        return ip_in_network(ip, self.destination, self.netmask)

    def code(self) -> str:
        """Single-letter route code, in the style of `show ip route`."""
        if self.kind is RouteKind.CONNECTED:
            return "C"
        return "S*" if self.is_default else "S"


@dataclass
class RoutingTable:
    routes: list[Route] = field(default_factory=list)

    def add(self, route: Route) -> None:
        self.routes.append(route)

    def add_connected(self, ip: str, netmask: str, interface_id: str) -> None:
        self.add(
            Route(
                destination=network_address(ip, netmask),
                netmask=netmask,
                interface_id=interface_id,
                gateway=None,
                kind=RouteKind.CONNECTED,
            )
        )

    def lookup(self, ip: str) -> Route | None:
        """Longest-prefix match, breaking ties on metric then insertion order."""
        candidates = [r for r in self.routes if r.matches(ip)]
        if not candidates:
            return None
        return min(candidates, key=lambda r: (-r.prefix_length, r.metric))

    def sorted_routes(self) -> list[Route]:
        """Display order: most specific first, matching real CLI output."""
        return sorted(self.routes, key=lambda r: (-r.prefix_length, r.destination))
