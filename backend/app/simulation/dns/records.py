"""DNS zone data and resolution.

Resolution follows CNAMEs the way a real resolver does, which is what makes a
CNAME pointing at a name that does not exist a genuinely confusing fault the
learner has to trace — exactly as it is in practice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..core.addressing import is_valid_ipv4

#: A CNAME chain longer than this is treated as a misconfiguration.
MAX_CNAME_DEPTH = 8


class DnsRecordType(str, Enum):
    A = "A"
    CNAME = "CNAME"
    MX = "MX"


class DnsStatus(str, Enum):
    NOERROR = "NOERROR"
    NXDOMAIN = "NXDOMAIN"
    #: The zone is broken: a CNAME loop, or a record whose value is not an address.
    SERVFAIL = "SERVFAIL"


def normalize_name(name: str) -> str:
    """DNS names are case-insensitive and the trailing dot is optional."""
    return (name or "").strip().lower().rstrip(".")


@dataclass
class DnsRecord:
    name: str
    type: DnsRecordType
    value: str
    priority: int = 10

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name)
        if self.type is not DnsRecordType.A:
            self.value = self.value.strip()
        else:
            self.value = self.value.strip()

    def display(self) -> str:
        if self.type is DnsRecordType.MX:
            return f"{self.name}  MX  {self.priority} {self.value}"
        return f"{self.name}  {self.type.value}  {self.value}"


@dataclass
class Resolution:
    status: DnsStatus
    #: The address the name finally resolved to, for an A lookup.
    address: str | None = None
    #: Every record consulted, in order — the CNAME trail plus the final answer.
    chain: list[DnsRecord] = field(default_factory=list)
    #: Records that directly answer the question (all MX records, say).
    answers: list[DnsRecord] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is DnsStatus.NOERROR


@dataclass
class DnsZone:
    records: list[DnsRecord] = field(default_factory=list)

    def matching(self, name: str, type: DnsRecordType) -> list[DnsRecord]:
        wanted = normalize_name(name)
        return [r for r in self.records if r.name == wanted and r.type is type]

    def has_name(self, name: str) -> bool:
        wanted = normalize_name(name)
        return any(r.name == wanted for r in self.records)

    def resolve(self, name: str, type: DnsRecordType = DnsRecordType.A) -> Resolution:
        wanted = normalize_name(name)
        if not wanted:
            return Resolution(DnsStatus.NXDOMAIN, detail="empty name")

        if type is DnsRecordType.MX:
            answers = sorted(self.matching(wanted, DnsRecordType.MX), key=lambda r: r.priority)
            if not answers:
                return Resolution(
                    DnsStatus.NXDOMAIN, detail=f"no MX record for {wanted}"
                )
            return Resolution(DnsStatus.NOERROR, answers=answers, chain=list(answers))

        # An A lookup may have to walk a chain of CNAMEs first.
        chain: list[DnsRecord] = []
        seen: set[str] = set()
        current = wanted

        for _ in range(MAX_CNAME_DEPTH):
            if current in seen:
                return Resolution(
                    DnsStatus.SERVFAIL,
                    chain=chain,
                    detail=f"CNAME loop involving {current}",
                )
            seen.add(current)

            direct = self.matching(current, DnsRecordType.A)
            if direct:
                record = direct[0]
                chain.append(record)
                if not is_valid_ipv4(record.value):
                    return Resolution(
                        DnsStatus.SERVFAIL,
                        chain=chain,
                        detail=f"A record for {current} is not a valid address: {record.value}",
                    )
                return Resolution(
                    DnsStatus.NOERROR,
                    address=record.value,
                    chain=chain,
                    answers=[record],
                )

            alias = self.matching(current, DnsRecordType.CNAME)
            if alias:
                record = alias[0]
                chain.append(record)
                current = normalize_name(record.value)
                continue

            return Resolution(
                DnsStatus.NXDOMAIN,
                chain=chain,
                detail=f"no A or CNAME record for {current}",
            )

        return Resolution(
            DnsStatus.SERVFAIL,
            chain=chain,
            detail=f"CNAME chain deeper than {MAX_CNAME_DEPTH} hops",
        )
