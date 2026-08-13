"""Router forwarding, routing tables and TTL."""

from app.schemas.topology import StaticRouteSchema
from app.simulation.routing.table import Route, RouteKind, RoutingTable
from app.simulation.runner import run_command
from builders import DEFAULT_MASK, TopologyBuilder, routed_network


def looping_routers() -> TopologyBuilder:
    """Two routers each pointing their default route at the other.

    Anything they cannot deliver bounces between them until the TTL runs out —
    the classic demonstration of why IPv4 has a hop limit at all.
    """
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
    net.router(
        "R1",
        [("192.168.1.1", DEFAULT_MASK), ("10.0.0.1", DEFAULT_MASK)],
        gateway="10.0.0.2",
    )
    net.router(
        "R2",
        [("10.0.0.2", DEFAULT_MASK), ("172.16.0.1", DEFAULT_MASK)],
        gateway="10.0.0.1",
    )
    net.link("PC-01", 0, "R1", 0)
    net.link("R1", 1, "R2", 0)
    return net


class TestRoutingTableUnit:
    def test_longest_prefix_wins(self):
        table = RoutingTable()
        table.add(Route("0.0.0.0", "0.0.0.0", "if-default", gateway="10.0.0.2", kind=RouteKind.DEFAULT))
        table.add(Route("10.0.0.0", "255.0.0.0", "if-a", gateway="10.0.0.3"))
        table.add(Route("10.1.0.0", "255.255.0.0", "if-b", gateway="10.0.0.4"))

        assert table.lookup("10.1.2.3").interface_id == "if-b"
        assert table.lookup("10.2.2.3").interface_id == "if-a"
        assert table.lookup("8.8.8.8").interface_id == "if-default"

    def test_no_match_returns_nothing(self):
        table = RoutingTable()
        table.add_connected("192.168.1.1", "255.255.255.0", "if-a")
        assert table.lookup("10.0.0.1") is None


class TestConnectedRoutes:
    def test_configuring_an_interface_creates_a_route(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("R1"), "show ip route")
        text = "\n".join(result.output)
        assert "C    192.168.1.0/24" in text
        assert "C    10.0.0.0/24" in text

    def test_an_unaddressed_router_has_no_routes(self):
        net = TopologyBuilder()
        net.router("R1", [(None, None), (None, None)])
        result = run_command(net.build(), net.device_id("R1"), "show ip route")
        assert "No routes in the routing table." in result.output

    def test_a_disabled_interface_contributes_no_route(self):
        net = routed_network()
        net.devices[2].interfaces[1].enabled = False
        result = run_command(net.build(), net.device_id("R1"), "show ip route")
        assert "10.0.0.0/24" not in "\n".join(result.output)


class TestStaticAndDefaultRoutes:
    def test_a_static_route_reaches_a_distant_subnet(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
        net.router(
            "R1",
            [("192.168.1.1", DEFAULT_MASK), ("10.0.0.1", DEFAULT_MASK)],
            static_routes=[
                StaticRouteSchema(
                    destination="172.16.0.0", netmask=DEFAULT_MASK, gateway="10.0.0.2"
                )
            ],
        )
        net.router("R2", [("10.0.0.2", DEFAULT_MASK), ("172.16.0.1", DEFAULT_MASK)],
                   static_routes=[
                       StaticRouteSchema(
                           destination="192.168.1.0", netmask=DEFAULT_MASK, gateway="10.0.0.1"
                       )
                   ])
        net.server("Server-01", "172.16.0.50", gateway="172.16.0.1")
        net.link("PC-01", 0, "R1", 0)
        net.link("R1", 1, "R2", 0)
        net.link("R2", 1, "Server-01", 0)

        result = run_command(net.build(), net.device_id("PC-01"), "ping 172.16.0.50 -n 1")
        assert result.success, "\n".join(result.output)

    def test_removing_the_return_route_breaks_the_ping(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
        net.router(
            "R1",
            [("192.168.1.1", DEFAULT_MASK), ("10.0.0.1", DEFAULT_MASK)],
            static_routes=[
                StaticRouteSchema(
                    destination="172.16.0.0", netmask=DEFAULT_MASK, gateway="10.0.0.2"
                )
            ],
        )
        # R2 has no way back to 192.168.1.0/24.
        net.router("R2", [("10.0.0.2", DEFAULT_MASK), ("172.16.0.1", DEFAULT_MASK)])
        net.server("Server-01", "172.16.0.50", gateway="172.16.0.1")
        net.link("PC-01", 0, "R1", 0)
        net.link("R1", 1, "R2", 0)
        net.link("R2", 1, "Server-01", 0)

        result = run_command(net.build(), net.device_id("PC-01"), "ping 172.16.0.50 -n 1")
        assert not result.success

    def test_the_default_route_is_shown_with_a_star(self):
        net = looping_routers()
        result = run_command(net.build(), net.device_id("R1"), "show ip route")
        assert "S*   0.0.0.0/0" in "\n".join(result.output)

    def test_a_next_hop_on_no_connected_subnet_is_ignored(self):
        net = TopologyBuilder()
        net.router("R1", [("192.168.1.1", DEFAULT_MASK)], gateway="10.9.9.9")
        result = run_command(net.build(), net.device_id("R1"), "show ip route")
        assert "0.0.0.0/0" not in "\n".join(result.output)


class TestNoRoute:
    def test_the_router_answers_with_destination_unreachable(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 172.16.5.5 -n 1")
        assert not result.success
        assert "unreachable" in "\n".join(result.output).lower()
        assert any(e.type == "route_miss" for e in result.events)

    def test_the_error_comes_from_the_router_that_dropped_it(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 172.16.5.5 -n 1")
        assert "Reply from 192.168.1.1" in "\n".join(result.output)


class TestTtl:
    def test_ttl_falls_by_one_per_router(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.0.50 -n 1")
        decrements = [e for e in result.events if e.type == "ttl_decrement"]
        assert len(decrements) == 2  # once each way

    def test_a_routing_loop_ends_in_time_exceeded(self):
        net = looping_routers()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 8.8.8.8 -n 1")
        assert not result.success
        assert "TTL expired in transit." in "\n".join(result.output)
        assert any(e.type == "ttl_expired" for e in result.events)

    def test_a_routing_loop_does_not_hang_the_engine(self):
        net = looping_routers()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 8.8.8.8 -n 1")
        # TTL 64 bounds the loop long before the engine's own hop limit.
        assert len([e for e in result.events if e.type == "frame_transmitted"]) < 200


class TestRouterAsAnEndpoint:
    def test_a_router_interface_answers_pings(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.1 -n 1")
        assert result.success

    def test_the_far_interface_of_a_router_also_answers(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.0.1 -n 1")
        assert result.success

    def test_a_router_can_ping_out_of_itself(self):
        net = routed_network()
        result = run_command(net.build(), net.device_id("R1"), "ping 10.0.0.50 -n 1")
        assert result.success
