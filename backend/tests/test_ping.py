"""End-to-end ping behaviour.

Every failure case here is a mistake a learner actually makes. The point of
these tests is that the simulator fails for the *right reason* — not that it
prints a canned error.
"""

from app.simulation.runner import run_command
from builders import DEFAULT_MASK, TopologyBuilder, routed_network, two_pc_lan


def ping(net: TopologyBuilder, source: str, target: str, count: int = 1):
    topology = net.build()
    return run_command(topology, net.device_id(source), f"ping {target} -n {count}")


def joined(result) -> str:
    return "\n".join(result.output)


class TestPingSucceeds:
    def test_across_a_switch(self):
        result = ping(two_pc_lan(), "PC-01", "192.168.1.20")
        assert result.success
        assert "Reply from 192.168.1.20" in joined(result)
        assert "Lost = 0 (0% loss)" in joined(result)

    def test_over_a_direct_cable_without_a_switch(self):
        net = TopologyBuilder()
        net.pc("PC-01", "10.10.10.1")
        net.pc("PC-02", "10.10.10.2")
        net.link("PC-01", 0, "PC-02", 0)
        assert ping(net, "PC-01", "10.10.10.2").success

    def test_across_a_router_into_another_subnet(self):
        result = ping(routed_network(), "PC-01", "10.0.0.50")
        assert result.success
        assert "Reply from 10.0.0.50" in joined(result)

    def test_ttl_is_decremented_by_each_router(self):
        result = ping(routed_network(), "PC-01", "10.0.0.50")
        # Left the server with TTL 64, crossed one router on the way back.
        assert "TTL=63" in joined(result)

    def test_repeated_pings_all_succeed(self):
        result = ping(two_pc_lan(), "PC-01", "192.168.1.20", count=4)
        assert "Sent = 4, Received = 4" in joined(result)


class TestPingFails:
    def test_when_the_cable_is_disconnected(self):
        net = two_pc_lan()
        net.links[1].status = "down"
        result = ping(net, "PC-01", "192.168.1.20")
        assert not result.success
        assert "Destination host unreachable." in joined(result)

    def test_when_there_is_no_cable_at_all(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10")
        net.pc("PC-02", "192.168.1.20")
        assert not ping(net, "PC-01", "192.168.1.20").success

    def test_when_the_subnet_mask_puts_hosts_on_different_networks(self):
        # Same wire, same /24 addresses — but PC-01's mask says PC-02 is remote,
        # and it has no gateway, so the packet never leaves.
        net = two_pc_lan()
        net.devices[0].interfaces[0].netmask = "255.255.255.192"
        net.devices[1].interfaces[0].ipv4 = "192.168.1.200"
        result = ping(net, "PC-01", "192.168.1.200")
        assert not result.success
        assert "Destination host unreachable." in joined(result)

    def test_when_the_target_has_no_ip_address(self):
        net = two_pc_lan()
        net.devices[1].interfaces[0].ipv4 = None
        result = ping(net, "PC-01", "192.168.1.20")
        assert not result.success
        assert "Request timed out." in joined(result) or "unreachable" in joined(result)

    def test_when_the_source_has_no_ip_address(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = None
        result = ping(net, "PC-01", "192.168.1.20")
        assert not result.success
        assert "no IPv4 address configured" in joined(result)

    def test_when_nobody_holds_the_target_address(self):
        result = ping(two_pc_lan(), "PC-01", "192.168.1.99")
        assert not result.success

    def test_when_the_default_gateway_is_missing(self):
        net = routed_network()
        net.devices[0].config.gateway = None
        result = ping(net, "PC-01", "10.0.0.50")
        assert not result.success
        assert "Destination host unreachable." in joined(result)

    def test_when_the_default_gateway_address_is_wrong(self):
        net = routed_network()
        net.devices[0].config.gateway = "192.168.1.254"  # nothing answers there
        result = ping(net, "PC-01", "10.0.0.50")
        assert not result.success

    def test_when_the_far_side_has_no_route_home(self):
        # The server can receive the echo request but has no gateway, so its
        # reply is dropped at its own doorstep.
        net = routed_network()
        net.devices[4].config.gateway = None
        result = ping(net, "PC-01", "10.0.0.50")
        assert not result.success
        assert "Request timed out." in joined(result)

    def test_when_the_router_has_no_route_to_the_destination(self):
        net = routed_network()
        result = ping(net, "PC-01", "172.16.5.5")
        assert not result.success
        assert "unreachable" in joined(result).lower()

    def test_when_an_interface_is_administratively_down(self):
        net = routed_network()
        net.devices[2].interfaces[1].enabled = False  # R1 eth1
        result = ping(net, "PC-01", "10.0.0.50")
        assert not result.success


class TestPingArguments:
    def test_rejects_a_non_address(self):
        result = ping(two_pc_lan(), "PC-01", "not-an-ip")
        assert not result.success
        assert "could not find host" in joined(result)

    def test_pinging_your_own_address_stays_local(self):
        result = ping(two_pc_lan(), "PC-01", "192.168.1.10")
        assert result.success
        assert "local interface" in joined(result)
        # Nothing was put on the wire.
        assert not result.packets


class TestPingSideEffects:
    def test_arp_cache_is_populated_by_a_successful_ping(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        state = result.device_state[net.device_id("PC-01")]
        assert state.arp_table.get("192.168.1.20")

    def test_switch_learns_both_hosts(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        state = result.device_state[net.device_id("Switch-01")]
        assert len(state.mac_table) == 2

    def test_the_event_trace_names_every_hop(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        transmitted = [e for e in result.events if e.type == "frame_transmitted"]
        assert transmitted
        assert all(e.link_id for e in transmitted)
        assert all(e.from_device_id and e.to_device_id for e in transmitted)

    def test_the_inspector_can_draw_a_full_path(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.0.50 -n 1")
        echo = [p for p in result.packets if p.icmp_type == "echo-request"]
        assert echo
        assert echo[0].path == ["PC-01", "SW-A", "R1"] or "SW-B" in echo[0].path
