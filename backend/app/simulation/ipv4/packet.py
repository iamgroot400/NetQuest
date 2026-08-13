"""IPv4 packet model.

Only the header fields the simulator actually acts on are modelled. Fragment
offsets, options and checksums are deliberately absent: nothing in the MVP
would read them, and a field nobody reads is a field that teaches nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

DEFAULT_TTL = 64


class IPProtocol(str, Enum):
    ICMP = "ICMP"


@dataclass
class IPv4Packet:
    src_ip: str
    dst_ip: str
    protocol: IPProtocol
    payload: Any
    ttl: int = DEFAULT_TTL
    # Total length in bytes, reported by ping as "bytes=".
    length: int = 32

    def decremented(self) -> "IPv4Packet":
        """Return a copy with TTL reduced by one, as a router would do."""
        return replace(self, ttl=self.ttl - 1)

    def summary(self) -> str:
        return f"IPv4 {self.src_ip} -> {self.dst_ip} ttl={self.ttl} proto={self.protocol.value}"
