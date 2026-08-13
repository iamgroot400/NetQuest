"""ARP packet model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..core.mac import BROADCAST_MAC


class ArpOperation(str, Enum):
    REQUEST = "request"
    REPLY = "reply"


# An ARP request does not know the target hardware address yet; RFC 826 leaves
# the field unspecified and implementations conventionally zero it.
UNKNOWN_MAC = "00:00:00:00:00:00"


@dataclass
class ArpPacket:
    operation: ArpOperation
    sender_mac: str
    sender_ip: str
    target_ip: str
    target_mac: str = UNKNOWN_MAC

    @classmethod
    def request(cls, sender_mac: str, sender_ip: str, target_ip: str) -> "ArpPacket":
        return cls(
            operation=ArpOperation.REQUEST,
            sender_mac=sender_mac,
            sender_ip=sender_ip,
            target_ip=target_ip,
            target_mac=UNKNOWN_MAC,
        )

    def reply(self, responder_mac: str) -> "ArpPacket":
        """Build the reply this request is asking for, with fields swapped."""
        return ArpPacket(
            operation=ArpOperation.REPLY,
            sender_mac=responder_mac,
            sender_ip=self.target_ip,
            target_ip=self.sender_ip,
            target_mac=self.sender_mac,
        )

    def summary(self) -> str:
        if self.operation is ArpOperation.REQUEST:
            return f"ARP Request: who has {self.target_ip}? tell {self.sender_ip}"
        return f"ARP Reply: {self.sender_ip} is at {self.sender_mac}"

    @property
    def destination_mac(self) -> str:
        """Requests are broadcast, replies are unicast back to the asker."""
        return BROADCAST_MAC if self.operation is ArpOperation.REQUEST else self.target_mac
