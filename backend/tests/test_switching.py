"""Layer 2 switch behaviour."""

from app.simulation.runner import run_command
from builders import TopologyBuilder, apply_state, two_pc_lan


def three_pc_lan() -> TopologyBuilder:
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10")
    net.pc("PC-02", "192.168.1.20")
    net.pc("PC-03", "192.168.1.30")
    net.switch("Switch-01", ports=4)
    net.link("PC-01", 0, "Switch-01", 0)
    net.link("PC-02", 0, "Switch-01", 1)
    net.link("PC-03", 0, "Switch-01", 2)
    return net


class TestMacLearning:
    def test_table_starts_empty(self):
        net = three_pc_lan()
        result = run_command(
            net.build(), net.device_id("Switch-01"), "show mac-address-table"
        )
        assert "The table is empty" in "\n".join(result.output)

    def test_learns_the_sender_and_the_responder(self):
        net = two_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        table = result.device_state[net.device_id("Switch-01")].mac_table
        assert len(table) == 2

    def test_learned_table_survives_a_round_trip(self):
        net = three_pc_lan()
        topology = net.build()
        apply_state(
            topology,
            run_command(topology, net.device_id("PC-01"), "ping 192.168.1.20 -n 1"),
        )

        shown = run_command(topology, net.device_id("Switch-01"), "show mac-address-table")
        assert "Total entries: 2" in "\n".join(shown.output)


class TestForwarding:
    def test_unknown_unicast_is_flooded(self):
        # PC-03 has never spoken, so its address is not in the table yet: the
        # very first frame to it must go out every port.
        net = three_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.30 -n 1")
        assert any(e.type == "frame_flooded" for e in result.events)
        assert result.success

    def test_known_unicast_goes_out_one_port_only(self):
        net = three_pc_lan()
        topology = net.build()
        pc1_id = net.device_id("PC-01")
        apply_state(topology, run_command(topology, pc1_id, "ping 192.168.1.20 -n 1"))

        result = run_command(topology, pc1_id, "ping 192.168.1.20 -n 1")
        assert result.success
        # With both hosts known and ARP cached, nothing needs flooding.
        assert not [e for e in result.events if e.type == "frame_flooded"]
        # PC-03 is never disturbed.
        assert not [e for e in result.events if e.device_name == "PC-03"]

    def test_a_frame_is_not_sent_back_out_the_port_it_arrived_on(self):
        net = three_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        for event in result.events:
            if event.type == "frame_transmitted":
                assert event.from_device_id != event.to_device_id

    def test_hosts_ignore_broadcasts_that_are_not_for_them(self):
        net = three_pc_lan()
        result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
        ignored = [
            e
            for e in result.events
            if e.device_name == "PC-03" and e.type == "frame_dropped"
        ]
        assert ignored, "PC-03 should have seen the flooded ARP and discarded it"


class TestSwitchCommands:
    def test_clear_empties_the_table(self):
        net = three_pc_lan()
        topology = net.build()
        switch_id = net.device_id("Switch-01")
        for device in topology.devices:
            if device.id == switch_id:
                device.runtime.mac_table = {"02:00:5E:00:00:00": f"{switch_id}-eth0"}

        result = run_command(topology, switch_id, "clear mac-address-table")
        assert "Cleared 1" in "\n".join(result.output)

    def test_a_switch_has_no_ip_commands(self):
        net = three_pc_lan()
        result = run_command(net.build(), net.device_id("Switch-01"), "ipconfig")
        assert not result.success
        assert "not recognised" in "\n".join(result.output)
