"""DNS query and response, carried as the payload of a UDP datagram."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .records import DnsRecord, DnsRecordType, DnsStatus, normalize_name

_ids = itertools.count(1)


@dataclass
class DnsQuery:
    name: str
    type: DnsRecordType = DnsRecordType.A
    transaction_id: int = field(default_factory=lambda: next(_ids))

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name)

    def summary(self) -> str:
        return f"DNS query {self.type.value} {self.name}"


@dataclass
class DnsResponse:
    name: str
    type: DnsRecordType
    status: DnsStatus
    transaction_id: int
    address: str | None = None
    answers: list[DnsRecord] = field(default_factory=list)
    chain: list[DnsRecord] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is DnsStatus.NOERROR

    def summary(self) -> str:
        if self.status is DnsStatus.NOERROR and self.address:
            return f"DNS response {self.name} → {self.address}"
        if self.status is DnsStatus.NOERROR and self.answers:
            return f"DNS response {self.name} → {len(self.answers)} record(s)"
        return f"DNS response {self.name} → {self.status.value}"
