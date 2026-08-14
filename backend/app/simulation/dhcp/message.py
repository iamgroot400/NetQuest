"""DHCP messages.

The four-step DISCOVER / OFFER / REQUEST / ACK exchange is modelled in full
rather than collapsed into one step, because seeing the OFFER arrive and the
ACK confirm it is most of the lesson.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

_transactions = itertools.count(1)


class DhcpMessageType(str, Enum):
    DISCOVER = "DISCOVER"
    OFFER = "OFFER"
    REQUEST = "REQUEST"
    ACK = "ACK"
    NAK = "NAK"
    RELEASE = "RELEASE"


@dataclass
class DhcpLease:
    """What a server hands out, and what a client then applies to itself."""

    ip: str
    netmask: str
    gateway: str | None = None
    dns: str | None = None
    lease_seconds: int = 86400
    server_ip: str | None = None

    def summary(self) -> str:
        parts = [f"{self.ip}/{self.netmask}"]
        if self.gateway:
            parts.append(f"gw {self.gateway}")
        if self.dns:
            parts.append(f"dns {self.dns}")
        return ", ".join(parts)


@dataclass
class DhcpMessage:
    type: DhcpMessageType
    client_mac: str
    transaction_id: int = field(default_factory=lambda: next(_transactions))
    #: Present on OFFER, REQUEST and ACK.
    lease: DhcpLease | None = None
    #: Why a NAK was sent — shown directly to the learner.
    reason: str = ""

    def summary(self) -> str:
        if self.lease and self.type in (
            DhcpMessageType.OFFER,
            DhcpMessageType.ACK,
            DhcpMessageType.REQUEST,
        ):
            return f"DHCP {self.type.value} {self.lease.summary()}"
        if self.type is DhcpMessageType.NAK and self.reason:
            return f"DHCP NAK ({self.reason})"
        return f"DHCP {self.type.value} from {self.client_mac}"
