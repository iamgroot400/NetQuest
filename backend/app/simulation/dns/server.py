"""The DNS server's answer, as a pure function of the zone and the question."""

from __future__ import annotations

from .message import DnsQuery, DnsResponse
from .records import DnsZone


def answer_query(zone: DnsZone, query: DnsQuery) -> DnsResponse:
    resolution = zone.resolve(query.name, query.type)
    return DnsResponse(
        name=query.name,
        type=query.type,
        status=resolution.status,
        transaction_id=query.transaction_id,
        address=resolution.address,
        answers=resolution.answers,
        chain=resolution.chain,
        detail=resolution.detail,
    )
