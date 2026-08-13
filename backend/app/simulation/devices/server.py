"""Server.

At the network layer a server behaves exactly like a workstation, so it shares
all of `Host`. It exists as its own type because topologies and challenges need
to talk about servers, and because application services (DNS, DHCP, HTTP) will
hang off this class in later versions.
"""

from __future__ import annotations

from .host import Host


class Server(Host):
    kind = "server"
