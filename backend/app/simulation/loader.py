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
from .core.models import DeviceConfig, Interface, Link, LinkEnd, StaticRouteConfig
from .core.network import Network
from .devices.base import Device
from .devices.pc import PC
from .devices.router import Router
from .devices.server import Server
from .devices.switch import Switch
from .routing.table import Route, RouteKind

#: Register a new device class here to make it loadable from a topology.
DEVICE_CLASSES: dict[DeviceType, type[Device]] = {
    DeviceType.PC: PC,
    DeviceType.SWITCH: Switch,
    DeviceType.ROUTER: Router,
    DeviceType.SERVER: Server,
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
    config = DeviceConfig(
        gateway=schema.config.gateway or None,
        static_routes=[
            StaticRouteConfig(
                destination=r.destination, netmask=r.netmask, gateway=r.gateway
            )
            for r in schema.config.static_routes
        ],
    )
    device = device_cls(id=schema.id, name=schema.name, interfaces=interfaces, config=config)
    device.load_state(schema.runtime.model_dump())

    if isinstance(device, Router):
        _build_routing_table(device)
    return device


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
