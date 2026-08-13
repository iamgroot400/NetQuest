"""Static configuration checks."""

from app.simulation.validation import validate_topology
from builders import DEFAULT_MASK, TopologyBuilder, two_pc_lan


def messages(topology, severity=None):
    result = validate_topology(topology)
    return [
        i.message
        for i in result.issues
        if severity is None or i.severity == severity
    ]


class TestCleanTopologies:
    def test_a_correct_lan_reports_nothing(self):
        assert validate_topology(two_pc_lan().build()).valid
        assert not validate_topology(two_pc_lan().build()).issues

    def test_an_empty_canvas_is_valid(self):
        assert validate_topology(TopologyBuilder().build()).valid


class TestAddressChecks:
    def test_a_malformed_address_is_an_error(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = "192.168.1.999"
        result = validate_topology(net.build())
        assert not result.valid
        assert "not a valid IPv4 address" in " ".join(messages(net.build()))

    def test_a_non_contiguous_mask_is_an_error(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].netmask = "255.0.255.0"
        assert not validate_topology(net.build()).valid
        assert "solid run of ones" in " ".join(messages(net.build()))

    def test_an_address_without_a_mask_is_an_error(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].netmask = None
        assert not validate_topology(net.build()).valid

    def test_the_network_address_cannot_be_assigned(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = "192.168.1.0"
        assert "network address" in " ".join(messages(net.build()))

    def test_the_broadcast_address_cannot_be_assigned(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = "192.168.1.255"
        assert "broadcast address" in " ".join(messages(net.build()))

    def test_duplicate_addresses_are_reported_once(self):
        net = two_pc_lan()
        net.devices[1].interfaces[0].ipv4 = "192.168.1.10"
        found = [m for m in messages(net.build()) if "Duplicate IP" in m]
        assert len(found) == 1
        assert "PC-01" in found[0] and "PC-02" in found[0]

    def test_a_cabled_interface_without_an_address_is_a_warning(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = None
        net.devices[0].interfaces[0].netmask = None
        result = validate_topology(net.build())
        assert result.valid, "a missing address is a warning, not a hard error"
        assert any("no IP address" in i.message for i in result.issues)


class TestGatewayChecks:
    def test_a_gateway_outside_every_local_subnet_is_an_error(self):
        net = two_pc_lan()
        net.devices[0].config.gateway = "10.9.9.1"
        assert not validate_topology(net.build()).valid
        assert "can never reach it" in " ".join(messages(net.build()))

    def test_a_valid_local_gateway_passes(self):
        net = two_pc_lan()
        net.devices[0].config.gateway = "192.168.1.1"
        assert validate_topology(net.build()).valid

    def test_a_malformed_gateway_is_an_error(self):
        net = two_pc_lan()
        net.devices[0].config.gateway = "nope"
        assert not validate_topology(net.build()).valid

    def test_pointing_the_gateway_at_yourself_is_a_warning(self):
        net = two_pc_lan()
        net.devices[0].config.gateway = "192.168.1.10"
        result = validate_topology(net.build())
        assert result.valid
        assert any("own address" in i.message for i in result.issues)


class TestCablingChecks:
    def test_two_cables_on_one_interface_is_an_error(self):
        net = two_pc_lan()
        net.link("PC-01", 0, "Switch-01", 3)  # PC-01 eth0 is already cabled
        assert not validate_topology(net.build()).valid
        assert "more than one cable" in " ".join(messages(net.build()))

    def test_switch_ports_need_no_addresses(self):
        net = TopologyBuilder()
        net.switch("Switch-01")
        assert validate_topology(net.build()).valid
        assert not validate_topology(net.build()).issues


class TestRouterChecks:
    def test_a_router_with_two_valid_subnets_is_clean(self):
        net = TopologyBuilder()
        net.router("Router-01", [("192.168.1.1", DEFAULT_MASK), ("10.0.0.1", DEFAULT_MASK)])
        assert validate_topology(net.build()).valid

    def test_overlapping_router_addresses_are_flagged_as_duplicates(self):
        net = TopologyBuilder()
        net.router("Router-01", [("192.168.1.1", DEFAULT_MASK), ("192.168.1.1", DEFAULT_MASK)])
        assert "Duplicate IP" in " ".join(messages(net.build()))
