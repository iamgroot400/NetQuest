"""ARP cache.

Entries never expire in the MVP. Real caches age out after a few minutes, but
the simulator has no wall clock and an entry that vanished between two commands
would look like a bug to a learner rather than a lesson.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.mac import normalize_mac


@dataclass
class ArpEntry:
    ip: str
    mac: str
    dynamic: bool = True

    @property
    def kind(self) -> str:
        return "dynamic" if self.dynamic else "static"


@dataclass
class ArpTable:
    entries: dict[str, ArpEntry] = field(default_factory=dict)

    def lookup(self, ip: str) -> str | None:
        entry = self.entries.get(ip)
        return entry.mac if entry else None

    def insert(self, ip: str, mac: str, dynamic: bool = True) -> bool:
        """Record a mapping. Returns True when something actually changed."""
        mac = normalize_mac(mac)
        existing = self.entries.get(ip)
        if existing and existing.mac == mac:
            return False
        self.entries[ip] = ArpEntry(ip=ip, mac=mac, dynamic=dynamic)
        return True

    def remove(self, ip: str) -> bool:
        return self.entries.pop(ip, None) is not None

    def clear(self) -> None:
        self.entries.clear()

    def to_dict(self) -> dict[str, str]:
        return {ip: entry.mac for ip, entry in self.entries.items()}

    @classmethod
    def from_dict(cls, data: dict[str, str] | None) -> "ArpTable":
        table = cls()
        for ip, mac in (data or {}).items():
            table.insert(ip, mac)
        return table
