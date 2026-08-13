from app.simulation.core.addressing import (
    broadcast_address,
    is_usable_host_ip,
    is_valid_ipv4,
    is_valid_netmask,
    netmask_to_prefix,
    network_address,
    prefix_to_netmask,
    same_subnet,
)
from app.simulation.core.mac import generate_mac, is_valid_mac, normalize_mac


class TestIPv4Validation:
    def test_accepts_ordinary_addresses(self):
        assert is_valid_ipv4("192.168.1.10")
        assert is_valid_ipv4("0.0.0.0")
        assert is_valid_ipv4("255.255.255.255")

    def test_rejects_malformed_addresses(self):
        assert not is_valid_ipv4("192.168.1")
        assert not is_valid_ipv4("192.168.1.256")
        assert not is_valid_ipv4("192.168.1.-1")
        assert not is_valid_ipv4("192.168.01.1")  # leading zero
        assert not is_valid_ipv4("hello")
        assert not is_valid_ipv4("")
        assert not is_valid_ipv4(None)


class TestNetmasks:
    def test_accepts_contiguous_masks(self):
        for mask in ("255.255.255.0", "255.255.0.0", "255.255.255.252", "0.0.0.0"):
            assert is_valid_netmask(mask), mask

    def test_rejects_non_contiguous_masks(self):
        assert not is_valid_netmask("255.0.255.0")
        assert not is_valid_netmask("255.255.255.1")

    def test_prefix_round_trip(self):
        for prefix in range(33):
            assert netmask_to_prefix(prefix_to_netmask(prefix)) == prefix


class TestSubnetMath:
    def test_network_and_broadcast(self):
        assert network_address("192.168.1.77", "255.255.255.0") == "192.168.1.0"
        assert broadcast_address("192.168.1.77", "255.255.255.0") == "192.168.1.255"

    def test_same_subnet_depends_on_the_mask(self):
        # The classic mistake: /24 keeps these apart, /16 puts them together.
        assert not same_subnet("192.168.1.10", "192.168.2.10", "255.255.255.0")
        assert same_subnet("192.168.1.10", "192.168.2.10", "255.255.0.0")

    def test_network_and_broadcast_are_not_host_addresses(self):
        assert not is_usable_host_ip("192.168.1.0", "255.255.255.0")
        assert not is_usable_host_ip("192.168.1.255", "255.255.255.0")
        assert is_usable_host_ip("192.168.1.1", "255.255.255.0")

    def test_point_to_point_masks_have_no_reserved_addresses(self):
        assert is_usable_host_ip("10.0.0.0", "255.255.255.254")


class TestMacAddresses:
    def test_generated_addresses_are_stable_and_unique(self):
        assert generate_mac(3, 1) == generate_mac(3, 1)
        assert generate_mac(3, 1) != generate_mac(3, 2)
        assert generate_mac(3, 1) != generate_mac(4, 1)
        assert is_valid_mac(generate_mac(1000, 5))

    def test_normalisation(self):
        assert normalize_mac("aa-bb-cc-dd-ee-01") == "AA:BB:CC:DD:EE:01"
        assert not is_valid_mac("AA:BB:CC:DD:EE")
        assert not is_valid_mac("ZZ:BB:CC:DD:EE:01")
