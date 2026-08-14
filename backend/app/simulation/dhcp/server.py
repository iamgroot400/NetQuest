"""The DHCP server's side of the exchange, as a pure function.

The pool is mutated when an address is committed, which is exactly the state a
learner needs to see when a pool runs dry.
"""

from __future__ import annotations

from .message import DhcpMessage, DhcpMessageType
from .pool import DhcpPool


def handle(
    message: DhcpMessage, pool: DhcpPool, server_ip: str | None
) -> DhcpMessage | None:
    """Produce the reply this message deserves, or None to stay silent."""

    if message.type is DhcpMessageType.DISCOVER:
        lease, reason = pool.allocate(message.client_mac)
        if lease is None:
            return DhcpMessage(
                type=DhcpMessageType.NAK,
                client_mac=message.client_mac,
                transaction_id=message.transaction_id,
                reason=reason,
            )
        lease.server_ip = server_ip
        return DhcpMessage(
            type=DhcpMessageType.OFFER,
            client_mac=message.client_mac,
            transaction_id=message.transaction_id,
            lease=lease,
        )

    if message.type is DhcpMessageType.REQUEST:
        # The client is confirming the offer. Re-allocating returns the same
        # address, so a second pass never consumes a second lease.
        lease, reason = pool.allocate(message.client_mac)
        if lease is None:
            return DhcpMessage(
                type=DhcpMessageType.NAK,
                client_mac=message.client_mac,
                transaction_id=message.transaction_id,
                reason=reason,
            )
        if message.lease and message.lease.ip != lease.ip:
            return DhcpMessage(
                type=DhcpMessageType.NAK,
                client_mac=message.client_mac,
                transaction_id=message.transaction_id,
                reason=f"{message.lease.ip} is not the address this server offered",
            )
        lease.server_ip = server_ip
        return DhcpMessage(
            type=DhcpMessageType.ACK,
            client_mac=message.client_mac,
            transaction_id=message.transaction_id,
            lease=lease,
        )

    if message.type is DhcpMessageType.RELEASE:
        pool.release(message.client_mac)
        return None

    return None
