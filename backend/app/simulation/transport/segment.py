"""TCP and UDP segments.

Only what the simulator reasons about is modelled: ports, and enough TCP flags
to show a handshake succeeding, being refused, or being silently dropped by a
firewall. There are no sequence numbers, windows or retransmissions — nothing
here would read them.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum
from typing import Any

_ephemeral = itertools.count(49152)

#: The private range real stacks draw client ports from.
EPHEMERAL_FLOOR = 49152
EPHEMERAL_CEILING = 65535


def next_ephemeral_port() -> int:
    """A client-side source port, wrapping inside the private range."""
    value = next(_ephemeral)
    span = EPHEMERAL_CEILING - EPHEMERAL_FLOOR + 1
    return EPHEMERAL_FLOOR + (value - EPHEMERAL_FLOOR) % span


class TransportProtocol(str, Enum):
    TCP = "TCP"
    UDP = "UDP"


class TcpFlag(str, Enum):
    SYN = "SYN"
    SYN_ACK = "SYN-ACK"
    ACK = "ACK"
    RST = "RST"
    FIN = "FIN"


@dataclass
class TransportSegment:
    protocol: TransportProtocol
    src_port: int
    dst_port: int
    #: TCP only. UDP is connectionless, so it stays None.
    flag: TcpFlag | None = None
    payload: Any = None

    @property
    def is_tcp(self) -> bool:
        return self.protocol is TransportProtocol.TCP

    def reply_ports(self) -> tuple[int, int]:
        """Source and destination for a segment going back the other way."""
        return self.dst_port, self.src_port

    def summary(self) -> str:
        flag = f" [{self.flag.value}]" if self.flag else ""
        return f"{self.protocol.value} {self.src_port} → {self.dst_port}{flag}"
