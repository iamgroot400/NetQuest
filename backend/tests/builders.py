"""Small fluent builder so tests read like network diagrams."""

from __future__ import annotations

from typing import Any

from app.schemas.topology import (
    DeviceConfigSchema,
    DeviceSchema,
    DeviceType,
    DhcpPoolSchema,
    DnsRecordSchema,
    FirewallRuleSchema,
    InterfaceSchema,
    LinkEndSchema,
    LinkSchema,
    NatSchema,
    ServiceSchema,
    StaticRouteSchema,
    TopologySchema,
    VpnSchema,
)
from app.simulation.core.mac import generate_mac

DEFAULT_MASK = "255.255.255.0"


def service(name: str, protocol: str, port: int, enabled: bool = True) -> ServiceSchema:
    return ServiceSchema(name=name, protocol=protocol, port=port, enabled=enabled)


def http(enabled: bool = True) -> ServiceSchema:
    return service("HTTP", "TCP", 80, enabled)


def https(enabled: bool = True) -> ServiceSchema:
    return service("HTTPS", "TCP", 443, enabled)


def dns_service(enabled: bool = True) -> ServiceSchema:
    return service("DNS", "UDP", 53, enabled)


def dhcp_service(enabled: bool = True) -> ServiceSchema:
    return service("DHCP", "UDP", 67, enabled)


def ssh(enabled: bool = True) -> ServiceSchema:
    return service("SSH", "TCP", 22, enabled)


def a_record(name: str, address: str) -> DnsRecordSchema:
    return DnsRecordSchema(name=name, type="A", value=address)


def cname(name: str, target: str) -> DnsRecordSchema:
    return DnsRecordSchema(name=name, type="CNAME", value=target)


def mx(name: str, target: str, priority: int = 10) -> DnsRecordSchema:
    return DnsRecordSchema(name=name, type="MX", value=target, priority=priority)


def allow(protocol: str = "any", port: int | None = None, **kwargs: Any) -> FirewallRuleSchema:
    return FirewallRuleSchema(action="allow", protocol=protocol, port=port, **kwargs)


def deny(protocol: str = "any", port: int | None = None, **kwargs: Any) -> FirewallRuleSchema:
    return FirewallRuleSchema(action="deny", protocol=protocol, port=port, **kwargs)


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
        **config: Any,
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
                gateway=gateway, static_routes=static_routes or [], **config
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
        **config: Any,
    ) -> DeviceSchema:
        return self._add(name, DeviceType.PC, [(ip, mask)], gateway, **config)

    def server(
        self,
        name: str,
        ip: str | None = None,
        mask: str | None = DEFAULT_MASK,
        gateway: str | None = None,
        **config: Any,
    ) -> DeviceSchema:
        return self._add(name, DeviceType.SERVER, [(ip, mask)], gateway, **config)

    def switch(self, name: str, ports: int = 8) -> DeviceSchema:
        return self._add(name, DeviceType.SWITCH, [(None, None)] * ports)

    def firewall(
        self,
        name: str,
        rules: list[FirewallRuleSchema] | None = None,
        default_policy: str = "allow",
        ports: int = 2,
    ) -> DeviceSchema:
        return self._add(
            name,
            DeviceType.FIREWALL,
            [(None, None)] * ports,
            firewall_rules=rules or [],
            firewall_default_policy=default_policy,
        )

    def router(
        self,
        name: str,
        interfaces: list[tuple[str | None, str | None]],
        gateway: str | None = None,
        static_routes: list[StaticRouteSchema] | None = None,
        **config: Any,
    ) -> DeviceSchema:
        return self._add(
            name, DeviceType.ROUTER, interfaces, gateway, static_routes, **config
        )

    # -- convenience presets ---------------------------------------------

    def web_server(
        self, name: str, ip: str, gateway: str | None = None, **config: Any
    ) -> DeviceSchema:
        config.setdefault("services", [http(), https()])
        return self.server(name, ip, DEFAULT_MASK, gateway, **config)

    def dns_server(
        self,
        name: str,
        ip: str,
        records: list[DnsRecordSchema],
        gateway: str | None = None,
        **config: Any,
    ) -> DeviceSchema:
        config.setdefault("services", [dns_service()])
        config["dns_records"] = records
        return self.server(name, ip, DEFAULT_MASK, gateway, **config)

    def dhcp_server(
        self,
        name: str,
        ip: str,
        pool: DhcpPoolSchema,
        gateway: str | None = None,
        **config: Any,
    ) -> DeviceSchema:
        config.setdefault("services", [dhcp_service()])
        config["dhcp_pool"] = pool
        return self.server(name, ip, DEFAULT_MASK, gateway, **config)

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
        device.runtime.dns_cache = dict(state.dns_cache)
        device.runtime.dhcp_leases = dict(state.dhcp_leases)
        device.runtime.firewall_hits = dict(state.firewall_hits)

        # A DHCP lease genuinely reconfigures the client, so it has to land in
        # the document itself rather than only in the learned-state block.
        assigned = state.assigned
        if assigned is not None:
            for iface in device.interfaces:
                if iface.id == assigned.interface_id:
                    iface.ipv4 = assigned.ipv4
                    iface.netmask = assigned.netmask
            device.config.gateway = assigned.gateway
            device.config.dns_server = assigned.dns_server
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


def campus_network(
    firewall_rules: list[FirewallRuleSchema] | None = None,
    default_policy: str = "allow",
) -> TopologyBuilder:
    """A small realistic site, used by most of the newer tests.

        PC-01 ─┐                                    ┌─ WEB-01  (HTTP, HTTPS)
        PC-02 ─┼─ Switch-01 ─ Firewall-01 ─ Router-01 ─ Switch-02 ─┼─ DNS-01  (UDP/53)
      DHCP-01 ─┘                                    └─ (10.0.2.0/24)

    Clients live in 10.0.1.0/24 and the servers in 10.0.2.0/24, so anything
    between them crosses both the firewall and the router.
    """
    net = TopologyBuilder()
    net.pc("PC-01", "10.0.1.10", gateway="10.0.1.1", dns_server="10.0.2.53")
    net.pc("PC-02", "10.0.1.11", gateway="10.0.1.1", dns_server="10.0.2.53")
    net.dhcp_server(
        "DHCP-01",
        "10.0.1.67",
        DhcpPoolSchema(
            start="10.0.1.100",
            end="10.0.1.110",
            netmask=DEFAULT_MASK,
            gateway="10.0.1.1",
            dns="10.0.2.53",
        ),
        gateway="10.0.1.1",
    )
    net.switch("Switch-01")
    net.firewall("Firewall-01", rules=firewall_rules, default_policy=default_policy)
    net.router("Router-01", [("10.0.1.1", DEFAULT_MASK), ("10.0.2.1", DEFAULT_MASK)])
    net.switch("Switch-02")
    net.web_server("WEB-01", "10.0.2.10", gateway="10.0.2.1")
    net.dns_server(
        "DNS-01",
        "10.0.2.53",
        [
            a_record("web.netquest.local", "10.0.2.10"),
            cname("www.netquest.local", "web.netquest.local"),
            a_record("dns.netquest.local", "10.0.2.53"),
            mx("netquest.local", "mail.netquest.local", 10),
        ],
        gateway="10.0.2.1",
    )

    net.link("PC-01", 0, "Switch-01", 0)
    net.link("PC-02", 0, "Switch-01", 1)
    net.link("DHCP-01", 0, "Switch-01", 2)
    net.link("Switch-01", 3, "Firewall-01", 0)
    net.link("Firewall-01", 1, "Router-01", 0)
    net.link("Router-01", 1, "Switch-02", 0)
    net.link("Switch-02", 1, "WEB-01", 0)
    net.link("Switch-02", 2, "DNS-01", 0)
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
