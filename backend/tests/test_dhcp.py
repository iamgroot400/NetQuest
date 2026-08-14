"""DHCP: the four-step exchange, pools, and the config it really applies.

A lease is only meaningful if it reconfigures the client for good, so most of
these tests check the topology document afterwards rather than just the output.
"""

from app.schemas.topology import DhcpPoolSchema
from app.simulation.dhcp.pool import DhcpPool
from app.simulation.runner import run_command, run_connection_test
from builders import DEFAULT_MASK, apply_state, campus_network, dhcp_service


def joined(result) -> str:
    return "\n".join(result.output)


def make_client(topology, name: str):
    """Strip a host's static addressing and make it a DHCP client."""
    device = next(d for d in topology.devices if d.name == name)
    device.interfaces[0].ipv4 = None
    device.config.gateway = None
    device.config.dns_server = None
    device.config.dhcp_client = True
    return device


def pool(**overrides) -> DhcpPoolSchema:
    defaults = dict(
        start="10.0.1.100",
        end="10.0.1.110",
        netmask=DEFAULT_MASK,
        gateway="10.0.1.1",
        dns="10.0.2.53",
    )
    defaults.update(overrides)
    return DhcpPoolSchema(**defaults)


class TestPoolUnit:
    def test_allocates_sequentially(self):
        p = DhcpPool(start="10.0.0.10", end="10.0.0.12", netmask=DEFAULT_MASK)
        assert p.allocate("aa:aa:aa:aa:aa:01")[0].ip == "10.0.0.10"
        assert p.allocate("aa:aa:aa:aa:aa:02")[0].ip == "10.0.0.11"

    def test_the_same_client_gets_the_same_address_back(self):
        p = DhcpPool(start="10.0.0.10", end="10.0.0.12", netmask=DEFAULT_MASK)
        first = p.allocate("aa:aa:aa:aa:aa:01")[0]
        second = p.allocate("AA:AA:AA:AA:AA:01")[0]
        assert first.ip == second.ip

    def test_exhaustion_is_reported_with_a_reason(self):
        p = DhcpPool(start="10.0.0.10", end="10.0.0.11", netmask=DEFAULT_MASK)
        p.allocate("aa:aa:aa:aa:aa:01")
        p.allocate("aa:aa:aa:aa:aa:02")
        lease, reason = p.allocate("aa:aa:aa:aa:aa:03")
        assert lease is None
        assert "no free addresses" in reason

    def test_releasing_frees_the_address(self):
        p = DhcpPool(start="10.0.0.10", end="10.0.0.10", netmask=DEFAULT_MASK)
        p.allocate("aa:aa:aa:aa:aa:01")
        assert p.allocate("aa:aa:aa:aa:aa:02")[0] is None
        assert p.release("aa:aa:aa:aa:aa:01")
        assert p.allocate("aa:aa:aa:aa:aa:02")[0].ip == "10.0.0.10"

    def test_a_disabled_pool_serves_nobody(self):
        p = DhcpPool(
            start="10.0.0.10", end="10.0.0.20", netmask=DEFAULT_MASK, enabled=False
        )
        lease, reason = p.allocate("aa:aa:aa:aa:aa:01")
        assert lease is None
        assert "disabled" in reason

    def test_a_gateway_outside_the_pool_subnet_is_detectable(self):
        good = DhcpPool(
            start="10.0.1.100", end="10.0.1.110", netmask=DEFAULT_MASK, gateway="10.0.1.1"
        )
        bad = DhcpPool(
            start="10.0.1.100", end="10.0.1.110", netmask=DEFAULT_MASK, gateway="10.9.9.1"
        )
        assert good.gateway_is_inside_pool_subnet()
        assert not bad.gateway_is_inside_pool_subnet()


class TestTheExchange:
    def test_a_client_gets_a_working_configuration(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")

        result = run_command(topology, client.id, "dhcp renew")
        assert result.success
        text = joined(result)
        assert "10.0.1.100" in text
        assert "10.0.1.1" in text
        assert "10.0.2.53" in text

    def test_all_four_steps_happen(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        result = run_command(topology, client.id, "dhcp renew")

        kinds = {e.type for e in result.events}
        assert {"dhcp_discover", "dhcp_offer", "dhcp_request", "dhcp_ack"} <= kinds

    def test_the_discover_really_is_a_broadcast(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        result = run_command(topology, client.id, "dhcp renew")

        discover = next(p for p in result.packets if p.dhcp_type == "DISCOVER")
        assert discover.dst_mac == "FF:FF:FF:FF:FF:FF"
        assert discover.src_ip == "0.0.0.0"
        assert discover.dst_port == 67

    def test_the_lease_lands_in_the_topology_document(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")

        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        assert client.interfaces[0].ipv4 == "10.0.1.100"
        assert client.interfaces[0].netmask == DEFAULT_MASK
        assert client.config.gateway == "10.0.1.1"
        assert client.config.dns_server == "10.0.2.53"

    def test_a_leased_client_can_then_do_real_work(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        ping = run_command(topology, client.id, "ping web.netquest.local -n 1")
        assert ping.success, joined(ping)

        reachable = run_connection_test(topology, client.id, "web.netquest.local", 80)
        assert reachable.reachable

    def test_releasing_gives_the_address_back(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        server = next(d for d in topology.devices if d.name == "DHCP-01")

        apply_state(topology, run_command(topology, client.id, "dhcp renew"))
        assert server.runtime.dhcp_leases

        apply_state(topology, run_command(topology, client.id, "dhcp release"))
        assert client.interfaces[0].ipv4 is None
        assert client.config.gateway is None
        assert server.runtime.dhcp_leases == {}

    def test_two_clients_get_different_addresses(self):
        net = campus_network()
        topology = net.build()
        first = make_client(topology, "PC-01")
        second = make_client(topology, "PC-02")

        apply_state(topology, run_command(topology, first.id, "dhcp renew"))
        apply_state(topology, run_command(topology, second.id, "dhcp renew"))

        assert first.interfaces[0].ipv4 != second.interfaces[0].ipv4

    def test_ipconfig_all_shows_the_lease(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        result = run_command(topology, client.id, "ipconfig /all")
        text = joined(result)
        assert "DHCP Enabled" in text
        assert "Lease Time" in text


class TestThingsThatGoWrong:
    def test_no_server_on_the_segment_means_no_lease(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        # Unplug the DHCP server.
        dhcp_link = next(
            link
            for link in topology.links
            if link.a.device_id == net.device_id("DHCP-01")
            or link.b.device_id == net.device_id("DHCP-01")
        )
        dhcp_link.status = "down"

        result = run_command(topology, client.id, "dhcp renew")
        assert not result.success
        assert "failed" in joined(result)

    def test_a_disabled_dhcp_service_means_no_lease(self):
        net = campus_network()
        topology = net.build()
        client = make_client(topology, "PC-02")
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.services = [dhcp_service(enabled=False)]

        assert not run_command(topology, client.id, "dhcp renew").success

    def test_an_exhausted_pool_refuses_with_a_reason(self):
        net = campus_network()
        topology = net.build()
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.dhcp_pool = pool(start="10.0.1.100", end="10.0.1.100")

        first = make_client(topology, "PC-01")
        second = make_client(topology, "PC-02")
        apply_state(topology, run_command(topology, first.id, "dhcp renew"))

        result = run_command(topology, second.id, "dhcp renew")
        assert not result.success
        naks = [e.message for e in result.events if e.type == "dhcp_nak"]
        assert any("no free addresses" in m for m in naks)

    def test_a_pool_handing_out_the_wrong_subnet_breaks_the_client(self):
        # The address applies fine, but it is not on the LAN, so nothing works.
        net = campus_network()
        topology = net.build()
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.dhcp_pool = pool(start="192.168.77.100", end="192.168.77.110")
        client = make_client(topology, "PC-02")

        apply_state(topology, run_command(topology, client.id, "dhcp renew"))
        assert client.interfaces[0].ipv4 == "192.168.77.100"

        ping = run_command(topology, client.id, "ping 10.0.1.10 -n 1")
        assert not ping.success

    def test_a_pool_with_the_wrong_gateway_breaks_only_remote_traffic(self):
        net = campus_network()
        topology = net.build()
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.dhcp_pool = pool(gateway="10.0.1.254")
        client = make_client(topology, "PC-02")
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        # The local network is fine…
        assert run_command(topology, client.id, "ping 10.0.1.10 -n 1").success
        # …but nothing beyond the router can be reached.
        assert not run_command(topology, client.id, "ping 10.0.2.10 -n 1").success

    def test_a_pool_with_the_wrong_dns_breaks_only_names(self):
        net = campus_network()
        topology = net.build()
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.dhcp_pool = pool(dns="10.0.2.99")
        client = make_client(topology, "PC-02")
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        # Addresses still work…
        assert run_command(topology, client.id, "ping 10.0.2.10 -n 1").success
        # …but names do not.
        by_name = run_command(topology, client.id, "ping web.netquest.local -n 1")
        assert not by_name.success

    def test_dhcp_does_not_cross_the_router(self):
        # DISCOVER is a broadcast, so a server on the far side never hears it.
        net = campus_network()
        topology = net.build()
        server = next(d for d in topology.devices if d.name == "DHCP-01")
        server.config.services = [dhcp_service(enabled=False)]

        far_side = next(d for d in topology.devices if d.name == "DNS-01")
        far_side.config.services = list(far_side.config.services) + [dhcp_service()]
        far_side.config.dhcp_pool = pool(start="10.0.2.200", end="10.0.2.210")

        client = make_client(topology, "PC-02")
        assert not run_command(topology, client.id, "dhcp renew").success
