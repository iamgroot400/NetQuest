"""NAT and VPN tunnelling.

Both are tested by contrast: the same request with the feature off and on. That
is the only way to show what the feature is actually doing.
"""

from app.schemas.topology import NatSchema, VpnSchema
from app.simulation.runner import run_command, run_connection_test
from builders import DEFAULT_MASK, TopologyBuilder, deny, service, ssh


def joined(result) -> str:
    return "\n".join(result.output)


def internet_edge(nat_enabled: bool) -> TopologyBuilder:
    """A private LAN behind a router, with an ISP that has no route back.

        PC-01 (192.168.1.10) ─ Router-01 ─ ISP-01 ─ SITE-01 (198.51.100.10)
                        private │ public 203.0.113.2

    ISP-01 deliberately knows nothing about 192.168.1.0/24, which is precisely
    why the private address has to be translated away.
    """
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
    router = net.router(
        "Router-01",
        [("192.168.1.1", DEFAULT_MASK), ("203.0.113.2", "255.255.255.252")],
        gateway="203.0.113.1",
    )
    net.router(
        "ISP-01", [("203.0.113.1", "255.255.255.252"), ("198.51.100.1", DEFAULT_MASK)]
    )
    net.web_server("SITE-01", "198.51.100.10", gateway="198.51.100.1")
    net.link("PC-01", 0, "Router-01", 0)
    net.link("Router-01", 1, "ISP-01", 0)
    net.link("ISP-01", 1, "SITE-01", 0)

    if nat_enabled:
        router.config.nat = NatSchema(
            enabled=True, outside_interface_id=router.interfaces[1].id
        )
    return net


class TestNat:
    def test_without_nat_the_private_address_leaks_and_nothing_returns(self):
        net = internet_edge(nat_enabled=False)
        result = run_connection_test(
            net.build(), net.device_id("PC-01"), "198.51.100.10", 80
        )
        assert not result.reachable
        # The ISP had no idea where to send the reply.
        assert "no route to 192.168.1.10" in (result.blocked_reason or "")

    def test_with_nat_the_same_request_succeeds(self):
        net = internet_edge(nat_enabled=True)
        result = run_connection_test(
            net.build(), net.device_id("PC-01"), "198.51.100.10", 80
        )
        assert result.reachable
        assert result.outcome == "open"

    def test_the_translation_is_recorded_and_reversed(self):
        net = internet_edge(nat_enabled=True)
        result = run_command(
            net.build(), net.device_id("PC-01"), "connect 198.51.100.10 80"
        )
        kinds = [e.type for e in result.events]
        assert "nat_translate" in kinds
        assert "nat_untranslate" in kinds

    def test_the_translation_table_is_visible(self):
        net = internet_edge(nat_enabled=True)
        result = run_command(
            net.build(), net.device_id("PC-01"), "connect 198.51.100.10 80"
        )
        state = result.device_state[net.device_id("Router-01")]
        assert len(state.nat_translations) == 1
        entry = state.nat_translations[0]
        assert entry.inside_ip == "192.168.1.10"
        assert entry.outside_ip == "203.0.113.2"
        assert entry.destination_ip == "198.51.100.10"

    def test_icmp_is_translated_too(self):
        net = internet_edge(nat_enabled=True)
        result = run_command(
            net.build(), net.device_id("PC-01"), "ping 198.51.100.10 -n 1"
        )
        assert result.success

    def test_the_server_only_ever_sees_the_public_address(self):
        net = internet_edge(nat_enabled=True)
        result = run_command(
            net.build(), net.device_id("PC-01"), "connect 198.51.100.10 80"
        )
        reached = [
            p
            for p in result.packets
            if p.path and p.path[-1] == "SITE-01" and p.dst_port == 80
        ]
        assert reached
        assert all(p.src_ip == "203.0.113.2" for p in reached)
        # The private address never leaves the router.
        assert not any(
            p.src_ip == "192.168.1.10" and p.path and "SITE-01" in p.path
            for p in result.packets
        )

    def test_unsolicited_inbound_traffic_has_nowhere_to_go(self):
        net = internet_edge(nat_enabled=True)
        result = run_connection_test(
            net.build(), net.device_id("SITE-01"), "203.0.113.2", 80
        )
        assert not result.reachable

    def test_show_ip_nat_translations_explains_itself_when_off(self):
        net = internet_edge(nat_enabled=False)
        result = run_command(
            net.build(), net.device_id("Router-01"), "show ip nat translations"
        )
        assert "NAT is not enabled" in joined(result)


def remote_access(vpn_enabled: bool) -> TopologyBuilder:
    """A remote laptop, a firewall that blocks SSH, and a VPN gateway behind it.

        LAPTOP-01 ─ Edge-01 ─ Firewall-01 ─ Switch-01 ─┬─ VPN-01 (UDP/1194)
                                                       └─ INTERNAL-01 (SSH)
    """
    net = TopologyBuilder()
    net.pc("LAPTOP-01", "198.51.100.50", gateway="198.51.100.1")
    net.router(
        "Edge-01", [("198.51.100.1", DEFAULT_MASK), ("10.8.0.1", DEFAULT_MASK)]
    )
    net.firewall(
        "Firewall-01", rules=[deny("tcp", 22, description="no SSH from outside")]
    )
    net.switch("Switch-01")
    net.server(
        "VPN-01",
        "10.8.0.10",
        gateway="10.8.0.1",
        services=[service("VPN", "UDP", 1194)],
        vpn=VpnSchema(is_gateway=True),
    )
    net.server("INTERNAL-01", "10.8.0.20", gateway="10.8.0.1", services=[ssh()])

    net.link("LAPTOP-01", 0, "Edge-01", 0)
    net.link("Edge-01", 1, "Firewall-01", 0)
    net.link("Firewall-01", 1, "Switch-01", 0)
    net.link("Switch-01", 1, "VPN-01", 0)
    net.link("Switch-01", 2, "INTERNAL-01", 0)

    if vpn_enabled:
        net.devices[0].config.vpn = VpnSchema(
            server="10.8.0.10",
            remote_network="10.8.0.0",
            remote_netmask=DEFAULT_MASK,
            tunnel_ip="10.8.0.200",
        )
    return net


class TestVpn:
    def test_without_a_tunnel_the_firewall_blocks_ssh(self):
        net = remote_access(vpn_enabled=False)
        result = run_connection_test(
            net.build(), net.device_id("LAPTOP-01"), "10.8.0.20", 22
        )
        assert not result.reachable
        assert result.blocked_at == "Firewall-01"

    def test_through_the_tunnel_the_same_ssh_gets_there(self):
        net = remote_access(vpn_enabled=True)
        result = run_connection_test(
            net.build(), net.device_id("LAPTOP-01"), "10.8.0.20", 22
        )
        assert result.reachable, result.detail

    def test_the_firewall_only_ever_sees_udp_1194(self):
        # The lesson: a tunnel is opaque to a filter that inspects ports.
        net = remote_access(vpn_enabled=True)
        result = run_command(
            net.build(), net.device_id("LAPTOP-01"), "connect 10.8.0.20 22"
        )
        decisions = [
            e.message for e in result.events if e.type.startswith("firewall_")
        ]
        assert decisions
        assert all("1194/udp" in m for m in decisions), decisions

    def test_the_packet_is_encapsulated_and_unwrapped(self):
        net = remote_access(vpn_enabled=True)
        result = run_command(
            net.build(), net.device_id("LAPTOP-01"), "connect 10.8.0.20 22"
        )
        kinds = [e.type for e in result.events]
        assert "vpn_encapsulate" in kinds
        assert "vpn_decapsulate" in kinds

    def test_the_inspector_can_see_both_header_layers(self):
        net = remote_access(vpn_enabled=True)
        result = run_command(
            net.build(), net.device_id("LAPTOP-01"), "connect 10.8.0.20 22"
        )
        tunnelled = [p for p in result.packets if p.encapsulated]
        assert tunnelled
        assert tunnelled[0].dst_port == 1194
        assert "10.8.0.20" in (tunnelled[0].inner_summary or "")

    def test_the_path_shows_the_traffic_going_via_the_gateway(self):
        net = remote_access(vpn_enabled=True)
        result = run_connection_test(
            net.build(), net.device_id("LAPTOP-01"), "10.8.0.20", 22
        )
        assert "VPN-01" in result.path
        assert result.path[-1] == "INTERNAL-01"

    def test_a_disabled_tunnel_falls_back_to_direct_traffic(self):
        net = remote_access(vpn_enabled=True)
        net.devices[0].config.vpn = VpnSchema(
            server="10.8.0.10",
            remote_network="10.8.0.0",
            remote_netmask=DEFAULT_MASK,
            tunnel_ip="10.8.0.200",
            enabled=False,
        )
        result = run_connection_test(
            net.build(), net.device_id("LAPTOP-01"), "10.8.0.20", 22
        )
        assert not result.reachable
        assert result.blocked_at == "Firewall-01"

    def test_a_gateway_that_is_not_listening_breaks_the_tunnel(self):
        net = remote_access(vpn_enabled=True)
        vpn = next(d for d in net.devices if d.name == "VPN-01")
        vpn.config.services = [service("VPN", "UDP", 1194, enabled=False)]
        result = run_connection_test(
            net.build(), net.device_id("LAPTOP-01"), "10.8.0.20", 22
        )
        assert not result.reachable

    def test_traffic_outside_the_tunnel_scope_is_not_wrapped(self):
        net = remote_access(vpn_enabled=True)
        result = run_command(
            net.build(), net.device_id("LAPTOP-01"), "ping 198.51.100.1 -n 1"
        )
        assert not any(e.type == "vpn_encapsulate" for e in result.events)
