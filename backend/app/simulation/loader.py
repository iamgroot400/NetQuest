"""Turn a topology document into a live `Network` of device objects.

This is the only bridge between the API's Pydantic schemas and the engine's
plain dataclasses, which keeps the engine free of any web framework.
"""

from __future__ import annotations

from ..schemas.topology import (
    DeviceSchema,
    DeviceType,
    TopologySchema,
)
from .core.addressing import (
    ANY_IPV4,
    is_valid_ipv4,
    is_valid_netmask,
    same_subnet,
)
from .core.models import (
    DeviceConfig,
    DhcpPoolConfig,
    DnsRecordConfig,
    FirewallRuleConfig,
    Interface,
    Link,
    LinkEnd,
    NatConfig,
    ServiceConfig,
    StaticRouteConfig,
    VpnConfig,
)
from .core.network import Network
from .devices.base import Device
from .devices.firewall import Firewall
from .devices.host import Host
from .devices.pc import PC
from .devices.router import Router
from .devices.server import Server
from .devices.switch import Switch
from .dhcp.message import DhcpLease
from .dhcp.pool import DhcpPool
from .dns.records import DnsRecord, DnsRecordType, DnsZone
from .routing.table import Route, RouteKind

#: Register a new device class here to make it loadable from a topology.
DEVICE_CLASSES: dict[DeviceType, type[Device]] = {
    DeviceType.PC: PC,
    DeviceType.SWITCH: Switch,
    DeviceType.ROUTER: Router,
    DeviceType.SERVER: Server,
    DeviceType.FIREWALL: Firewall,
}


def build_device(schema: DeviceSchema) -> Device:
    device_cls = DEVICE_CLASSES[schema.type]
    interfaces = [
        Interface(
            id=i.id,
            name=i.name,
            mac=i.mac,
            device_id=schema.id,
            ipv4=i.ipv4 or None,
            netmask=i.netmask or None,
            enabled=i.enabled,
        )
        for i in schema.interfaces
    ]
    config = _build_config(schema)
    device = device_cls(id=schema.id, name=schema.name, interfaces=interfaces, config=config)
    device.load_state(schema.runtime.model_dump())

    if isinstance(device, Host):
        _attach_host_services(device, schema)
    if isinstance(device, Router):
        _build_routing_table(device)
    return device


def _build_config(schema: DeviceSchema) -> DeviceConfig:
    raw = schema.config
    return DeviceConfig(
        gateway=raw.gateway or None,
        dns_server=raw.dns_server or None,
        dhcp_client=raw.dhcp_client,
        static_routes=[
            StaticRouteConfig(
                destination=r.destination, netmask=r.netmask, gateway=r.gateway
            )
            for r in raw.static_routes
        ],
        services=[
            ServiceConfig(
                name=s.name,
                protocol=s.protocol.upper(),
                port=s.port,
                enabled=s.enabled,
            )
            for s in raw.services
        ],
        dns_records=[
            DnsRecordConfig(
                name=r.name, type=r.type.upper(), value=r.value, priority=r.priority
            )
            for r in raw.dns_records
        ],
        dhcp_pool=(
            DhcpPoolConfig(
                start=raw.dhcp_pool.start,
                end=raw.dhcp_pool.end,
                netmask=raw.dhcp_pool.netmask,
                gateway=raw.dhcp_pool.gateway or None,
                dns=raw.dhcp_pool.dns or None,
                lease_seconds=raw.dhcp_pool.lease_seconds,
                enabled=raw.dhcp_pool.enabled,
            )
            if raw.dhcp_pool
            else None
        ),
        firewall_rules=[
            FirewallRuleConfig(
                action=r.action.lower(),
                protocol=(r.protocol or "any").lower(),
                port=r.port,
                source=r.source or "any",
                destination=r.destination or "any",
                description=r.description,
            )
            for r in raw.firewall_rules
        ],
        firewall_default_policy=(raw.firewall_default_policy or "allow").lower(),
        nat=(
            NatConfig(
                enabled=raw.nat.enabled,
                outside_interface_id=raw.nat.outside_interface_id or None,
            )
            if raw.nat
            else None
        ),
        vpn=(
            VpnConfig(
                server=raw.vpn.server or None,
                remote_network=raw.vpn.remote_network or None,
                remote_netmask=raw.vpn.remote_netmask or None,
                tunnel_ip=raw.vpn.tunnel_ip or None,
                is_gateway=raw.vpn.is_gateway,
                enabled=raw.vpn.enabled,
            )
            if raw.vpn
            else None
        ),
    )


def _attach_host_services(host: Host, schema: DeviceSchema) -> None:
    """Give a host the zone and pool its configuration describes."""
    records = []
    for record in host.config.dns_records:
        try:
            record_type = DnsRecordType(record.type.upper())
        except ValueError:
            # An unknown record type is skipped rather than crashing the load;
            # the validation endpoint reports it to the user.
            continue
        records.append(
            DnsRecord(
                name=record.name,
                type=record_type,
                value=record.value,
                priority=record.priority,
            )
        )
    host.dns_zone = DnsZone(records=records)

    pool_config = host.config.dhcp_pool
    if pool_config is not None:
        pool = DhcpPool(
            start=pool_config.start,
            end=pool_config.end,
            netmask=pool_config.netmask,
            gateway=pool_config.gateway,
            dns=pool_config.dns,
            lease_seconds=pool_config.lease_seconds,
            enabled=pool_config.enabled,
        )
        pool.load_leases(schema.runtime.dhcp_leases)
        host.dhcp_pool = pool

    # A client that already holds a DHCP address needs to know that across
    # separate commands, otherwise `dhcp release` would find nothing to give up
    # and `ipconfig /all` would not report the lease.
    if host.config.dhcp_client:
        iface = host.first_enabled_interface
        if iface is not None and iface.has_ip:
            assert iface.ipv4 and iface.netmask
            host.dhcp_lease = DhcpLease(
                ip=iface.ipv4,
                netmask=iface.netmask,
                gateway=host.config.gateway,
                dns=host.config.dns_server,
            )


def _build_routing_table(router: Router) -> None:
    """Connected subnets first, then static routes, then the default route."""
    for iface in router.interfaces:
        if iface.enabled and iface.has_ip:
            assert iface.ipv4 and iface.netmask
            router.routing_table.add_connected(iface.ipv4, iface.netmask, iface.id)

    for static in router.config.static_routes:
        if not (is_valid_ipv4(static.destination) and is_valid_netmask(static.netmask)):
            continue
        if not is_valid_ipv4(static.gateway):
            continue
        exit_iface = _interface_reaching(router, static.gateway)
        if exit_iface is None:
            # A next hop that is not on any connected subnet is unusable; the
            # validation endpoint reports this to the user.
            continue
        router.routing_table.add(
            Route(
                destination=static.destination,
                netmask=static.netmask,
                interface_id=exit_iface.id,
                gateway=static.gateway,
                kind=RouteKind.STATIC,
            )
        )

    gateway = router.config.gateway
    if is_valid_ipv4(gateway):
        assert gateway
        exit_iface = _interface_reaching(router, gateway)
        if exit_iface is not None:
            router.routing_table.add(
                Route(
                    destination=ANY_IPV4,
                    netmask=ANY_IPV4,
                    interface_id=exit_iface.id,
                    gateway=gateway,
                    kind=RouteKind.DEFAULT,
                )
            )


def _interface_reaching(router: Router, ip: str) -> Interface | None:
    for iface in router.ip_interfaces:
        assert iface.ipv4 and iface.netmask
        if same_subnet(iface.ipv4, ip, iface.netmask):
            return iface
    return None


def build_network(topology: TopologySchema) -> Network:
    devices = [build_device(d) for d in topology.devices]
    known_interfaces = {i.id for d in devices for i in d.interfaces}
    links = [
        Link(
            id=link.id,
            a=LinkEnd(device_id=link.a.device_id, interface_id=link.a.interface_id),
            b=LinkEnd(device_id=link.b.device_id, interface_id=link.b.interface_id),
            status=link.status,
        )
        for link in topology.links
        # Skip cables pointing at interfaces that no longer exist.
        if link.a.interface_id in known_interfaces and link.b.interface_id in known_interfaces
    ]
    return Network(devices=devices, links=links)


def collect_state(network: Network) -> dict[str, dict]:
    """Learned tables for every device, to be written back by the frontend."""
    return {device_id: device.state() for device_id, device in network.devices.items()}
