"""Small fluent builder so tests read like network diagrams."""

from __future__ import annotations

from app.schemas.topology import (
    DeviceConfigSchema,
    DeviceSchema,
    DeviceType,
    InterfaceSchema,
    LinkEndSchema,
    LinkSchema,
    StaticRouteSchema,
    TopologySchema,
)
from app.simulation.core.mac import generate_mac

DEFAULT_MASK = "255.255.255.0"


class TopologyBuilder:
    def __init__(self) -> None:
        self.devices: list[DeviceSchema] = []
        self.links: list[LinkSchema] = []
        self._by_name: dict[str, DeviceSchema] = {}

    # -- devices ---------------------------------------------------------

    def _add(
        self,
        name: str,
        type: DeviceType,
        ports: list[tuple[str | None, str | None]],
        gateway: str | None = None,
        static_routes: list[StaticRouteSchema] | None = None,
    ) -> DeviceSchema:
        index = len(self.devices)
        device = DeviceSchema(
            id=f"dev-{index}",
            type=type,
            name=name,
            interfaces=[
                InterfaceSchema(
                    id=f"dev-{index}-eth{port_index}",
                    name=f"eth{port_index}",
                    mac=generate_mac(index, port_index),
                    ipv4=ip,
                    netmask=mask,
                )
                for port_index, (ip, mask) in enumerate(ports)
            ],
            config=DeviceConfigSchema(
                gateway=gateway, static_routes=static_routes or []
            ),
        )
        self.devices.append(device)
        self._by_name[name] = device
        return device

    def pc(
        self,
        name: str,
        ip: str | None = None,
        mask: str | None = DEFAULT_MASK,
        gateway: str | None = None,
    ) -> DeviceSchema:
        return self._add(name, DeviceType.PC, [(ip, mask)], gateway)

    def server(
        self,
        name: str,
        ip: str | None = None,
        mask: str | None = DEFAULT_MASK,
        gateway: str | None = None,
    ) -> DeviceSchema:
        return self._add(name, DeviceType.SERVER, [(ip, mask)], gateway)

    def switch(self, name: str, ports: int = 8) -> DeviceSchema:
        return self._add(name, DeviceType.SWITCH, [(None, None)] * ports)

    def router(
        self,
        name: str,
        interfaces: list[tuple[str | None, str | None]],
        gateway: str | None = None,
        static_routes: list[StaticRouteSchema] | None = None,
    ) -> DeviceSchema:
        return self._add(name, DeviceType.ROUTER, interfaces, gateway, static_routes)

    # -- cabling ---------------------------------------------------------

    def link(
        self,
        a_name: str,
        a_port: int,
        b_name: str,
        b_port: int,
        status: str = "up",
    ) -> LinkSchema:
        a = self._by_name[a_name]
        b = self._by_name[b_name]
        link = LinkSchema(
            id=f"lnk-{len(self.links)}",
            a=LinkEndSchema(device_id=a.id, interface_id=a.interfaces[a_port].id),
            b=LinkEndSchema(device_id=b.id, interface_id=b.interfaces[b_port].id),
            status=status,
        )
        self.links.append(link)
        return link

    # -- output ----------------------------------------------------------

    def device_id(self, name: str) -> str:
        return self._by_name[name].id

    def build(self) -> TopologySchema:
        return TopologySchema(devices=self.devices, links=self.links)


def apply_state(topology: TopologySchema, result) -> TopologySchema:
    """Write learned tables back into the document.

    This is exactly what the frontend does between two commands, so tests that
    need a warmed-up network must do it too — otherwise only the device you
    poked remembers anything.
    """
    for device in topology.devices:
        state = result.device_state.get(device.id)
        if state is None:
            continue
        device.runtime.arp_table = dict(state.arp_table)
        device.runtime.mac_table = dict(state.mac_table)
    return topology


def two_pc_lan() -> TopologyBuilder:
    """PC-01 ── Switch-01 ── PC-02, all in 192.168.1.0/24."""
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10")
    net.pc("PC-02", "192.168.1.20")
    net.switch("Switch-01", ports=4)
    net.link("PC-01", 0, "Switch-01", 0)
    net.link("PC-02", 0, "Switch-01", 1)
    return net


def routed_network() -> TopologyBuilder:
    """Two subnets joined by a router.

    PC-01 (192.168.1.10) ── SW-A ── R1 eth0 192.168.1.1
                                    R1 eth1 10.0.0.1 ── SW-B ── Server-01 (10.0.0.50)
    """
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
    net.switch("SW-A", ports=4)
    net.router("R1", [("192.168.1.1", DEFAULT_MASK), ("10.0.0.1", DEFAULT_MASK)])
    net.switch("SW-B", ports=4)
    net.server("Server-01", "10.0.0.50", gateway="10.0.0.1")
    net.link("PC-01", 0, "SW-A", 0)
    net.link("SW-A", 1, "R1", 0)
    net.link("R1", 1, "SW-B", 0)
    net.link("SW-B", 1, "Server-01", 0)
    return net
