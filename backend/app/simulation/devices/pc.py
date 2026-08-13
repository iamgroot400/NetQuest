"""End-user workstation."""

from __future__ import annotations

from .host import Host


class PC(Host):
    kind = "pc"
