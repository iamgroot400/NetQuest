"""Ethernet II framing."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..core.mac import is_broadcast_mac, normalize_mac

_frame_counter = itertools.count(1)
_flow_counter = itertools.count(1)


def next_flow_id() -> str:
    """A flow id follows one logical packet end to end.

    A router re-encapsulates an IPv4 packet into a brand new frame, so frame
    ids change at every hop. The flow id survives that, which is what lets the
    packet inspector draw a complete path from source to destination.
    """
    return f"flow-{next(_flow_counter)}"


class EtherType(str, Enum):
    IPV4 = "IPv4"
    ARP = "ARP"


@dataclass
class EthernetFrame:
    src_mac: str
    dst_mac: str
    ethertype: EtherType
    payload: Any
    flow_id: str = field(default_factory=next_flow_id)
    uid: str = field(default_factory=lambda: f"frame-{next(_frame_counter)}")

    def __post_init__(self) -> None:
        self.src_mac = normalize_mac(self.src_mac)
        self.dst_mac = normalize_mac(self.dst_mac)

    @property
    def is_broadcast(self) -> bool:
        return is_broadcast_mac(self.dst_mac)

    def addressed_to(self, mac: str) -> bool:
        """True if a NIC with this MAC would accept the frame."""
        return self.is_broadcast or self.dst_mac == normalize_mac(mac)

    def summary(self) -> str:
        return f"{self.ethertype.value} {self.src_mac} -> {self.dst_mac}"
