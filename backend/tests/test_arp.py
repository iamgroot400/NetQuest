"""ARP resolution."""

from app.simulation.runner import run_command
from builders import TopologyBuilder, apply_state, two_pc_lan


class TestResolution:
    def test_a_request_is_broadcast_and_answered(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")

        requests = [e for e in result.events if e.type == "arp_request"]
        replies = [e for e in result.events if e.type == "arp_reply"]
        assert len(requests) == 1
        assert replies

        request_packet = next(p for p in result.packets if p.arp_operation == "request")
        assert request_packet.dst_mac == "FF:FF:FF:FF:FF:FF"
        assert request_packet.arp_target_ip == "192.168.1.20"

    def test_the_reply_is_unicast_back_to_the_asker(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        reply = next(p for p in result.packets if p.arp_operation == "reply")
        assert reply.dst_mac != "FF:FF:FF:FF:FF:FF"
        assert reply.arp_sender_ip == "192.168.1.20"

    def test_resolution_fails_when_nobody_owns_the_address(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.77 -n 1")
        assert any(e.type == "arp_failed" for e in result.events)
        assert not result.success

    def test_the_sender_only_asks_once_for_four_pings(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 4")
        from_pc1 = [e for e in result.events if e.device_name == "PC-01"]
        assert len([e for e in from_pc1 if e.type == "arp_request"]) == 1
        # The remaining three pings are answered straight from the cache.
        assert len([e for e in from_pc1 if e.type == "arp_cache_hit"]) == 3


class TestCache:
    def test_a_warmed_up_network_sends_no_broadcasts_at_all(self):
        net = two_pc_lan()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        first = run_command(topology, pc1, "ping 192.168.1.20 -n 1")
        apply_state(topology, first)

        second = run_command(topology, pc1, "ping 192.168.1.20 -n 1")
        assert not [e for e in second.events if e.type == "arp_request"]
        assert any(e.type == "arp_cache_hit" for e in second.events)

    def test_the_responder_must_arp_when_only_the_sender_is_cached(self):
        # Restoring one side only is not a shortcut: PC-02 never saw a request
        # this time round, so it has to ask before it can answer.
        net = two_pc_lan()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        first = run_command(topology, pc1, "ping 192.168.1.20 -n 1")
        for device in topology.devices:
            if device.id == pc1:
                device.runtime.arp_table = dict(first.device_state[pc1].arp_table)

        second = run_command(topology, pc1, "ping 192.168.1.20 -n 1")
        asked = [e for e in second.events if e.type == "arp_request"]
        assert [e.device_name for e in asked] == ["PC-02"]
        assert second.success

    def test_the_arp_command_shows_learned_entries(self):
        net = two_pc_lan()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        apply_state(topology, run_command(topology, pc1, "ping 192.168.1.20 -n 1"))

        shown = run_command(topology, pc1, "arp")
        text = "\n".join(shown.output)
        assert "192.168.1.20" in text
        assert "dynamic" in text

    def test_arp_dash_d_empties_the_cache(self):
        net = two_pc_lan()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        for device in topology.devices:
            if device.id == pc1:
                device.runtime.arp_table = {"192.168.1.20": "02:00:5E:00:01:00"}

        cleared = run_command(topology, pc1, "arp -d")
        assert "cleared" in "\n".join(cleared.output).lower()
        assert cleared.device_state[pc1].arp_table == {}

    def test_empty_cache_says_so(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "arp")
        assert "No ARP entries found." in result.output


class TestArpAcrossSubnets:
    def test_a_host_arps_for_its_gateway_not_the_far_destination(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10", gateway="192.168.1.1")
        net.router("R1", [("192.168.1.1", "255.255.255.0"), ("10.0.0.1", "255.255.255.0")])
        net.server("Server-01", "10.0.0.50", gateway="10.0.0.1")
        net.link("PC-01", 0, "R1", 0)
        net.link("R1", 1, "Server-01", 0)

        result = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.0.50 -n 1")
        assert result.success

        asked_by_pc = [
            p
            for p in result.packets
            if p.arp_operation == "request" and p.arp_sender_ip == "192.168.1.10"
        ]
        assert len(asked_by_pc) == 1
        assert asked_by_pc[0].arp_target_ip == "192.168.1.1"
