"""DHCP address pool and lease bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.addressing import (
    is_valid_ipv4,
    is_valid_netmask,
    iter_range,
    network_address,
    same_subnet,
)
from ..core.mac import normalize_mac
from .message import DhcpLease


@dataclass
class DhcpPool:
    start: str
    end: str
    netmask: str
    gateway: str | None = None
    dns: str | None = None
    lease_seconds: int = 86400
    enabled: bool = True
    #: MAC -> address, so a client that asks twice gets the same lease back.
    leases: dict[str, str] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return (
            self.enabled
            and is_valid_ipv4(self.start)
            and is_valid_ipv4(self.end)
            and is_valid_netmask(self.netmask)
        )

    def addresses(self) -> list[str]:
        return list(iter_range(self.start, self.end))

    def taken(self) -> set[str]:
        return set(self.leases.values())

    def allocate(self, client_mac: str) -> tuple[DhcpLease | None, str]:
        """Reserve an address for this client.

        Returns (lease, reason). A None lease means the pool could not serve
        the request, and the reason is shown to the learner verbatim.
        """
        if not self.is_usable:
            return None, "the pool is disabled or misconfigured"

        mac = normalize_mac(client_mac)
        existing = self.leases.get(mac)
        if existing:
            return self._lease_for(existing), "renewed existing lease"

        taken = self.taken()
        for candidate in self.addresses():
            if candidate not in taken:
                self.leases[mac] = candidate
                return self._lease_for(candidate), "new lease"

        return None, f"the pool {self.start}-{self.end} has no free addresses left"

    def release(self, client_mac: str) -> bool:
        return self.leases.pop(normalize_mac(client_mac), None) is not None

    def _lease_for(self, ip: str) -> DhcpLease:
        return DhcpLease(
            ip=ip,
            netmask=self.netmask,
            gateway=self.gateway or None,
            dns=self.dns or None,
            lease_seconds=self.lease_seconds,
        )

    # -- diagnostics the UI and CLI surface -------------------------------

    def gateway_is_inside_pool_subnet(self) -> bool:
        """A gateway outside the handed-out subnet leaves clients stranded."""
        if not (self.gateway and is_valid_ipv4(self.gateway) and self.is_usable):
            return True
        return same_subnet(self.start, self.gateway, self.netmask)

    def pool_subnet(self) -> str | None:
        if not self.is_usable:
            return None
        return network_address(self.start, self.netmask)

    def capacity(self) -> int:
        return len(self.addresses())

    def to_dict(self) -> dict[str, str]:
        return dict(self.leases)

    def load_leases(self, leases: dict[str, str] | None) -> None:
        for mac, ip in (leases or {}).items():
            self.leases[normalize_mac(mac)] = ip
