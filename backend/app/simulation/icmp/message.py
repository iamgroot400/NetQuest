"""ICMP messages.

Types are spelled out as readable names rather than numbers because the packet
inspector shows them directly to the learner.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ECHO_PAYLOAD_BYTES = 32


class IcmpType(str, Enum):
    ECHO_REQUEST = "echo-request"
    ECHO_REPLY = "echo-reply"
    DESTINATION_UNREACHABLE = "destination-unreachable"
    TIME_EXCEEDED = "time-exceeded"


class IcmpCode(str, Enum):
    NONE = ""
    NET_UNREACHABLE = "net-unreachable"
    HOST_UNREACHABLE = "host-unreachable"
    PORT_UNREACHABLE = "port-unreachable"
    ADMINISTRATIVELY_PROHIBITED = "administratively-prohibited"
    TTL_EXCEEDED_IN_TRANSIT = "ttl-exceeded-in-transit"


#: Errors must never trigger further errors, or a routing loop turns into an
#: infinite storm of unreachable messages.
ERROR_TYPES = {IcmpType.DESTINATION_UNREACHABLE, IcmpType.TIME_EXCEEDED}


@dataclass
class IcmpMessage:
    type: IcmpType
    identifier: int = 1
    sequence: int = 1
    code: IcmpCode = IcmpCode.NONE
    payload_bytes: int = ECHO_PAYLOAD_BYTES

    @property
    def is_error(self) -> bool:
        return self.type in ERROR_TYPES

    def echo_reply(self) -> "IcmpMessage":
        return IcmpMessage(
            type=IcmpType.ECHO_REPLY,
            identifier=self.identifier,
            sequence=self.sequence,
            payload_bytes=self.payload_bytes,
        )

    def summary(self) -> str:
        if self.type in (IcmpType.ECHO_REQUEST, IcmpType.ECHO_REPLY):
            return f"ICMP {self.type.value} id={self.identifier} seq={self.sequence}"
        suffix = f" ({self.code.value})" if self.code is not IcmpCode.NONE else ""
        return f"ICMP {self.type.value}{suffix}"
