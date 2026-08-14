"""Listening ports, TCP handshakes, and the firewall that filters them.

The distinction these tests protect is *refused* versus *filtered*: a closed
port answers with RST, while a firewall drop produces silence. Confusing the
two is the most common wrong turn in real troubleshooting.
"""

from app.schemas.topology import FirewallRuleSchema
from app.simulation.runner import run_command, run_connection_test
from builders import (
    DEFAULT_MASK,
    TopologyBuilder,
    allow,
    apply_state,
    campus_network,
    deny,
    http,
    https,
    ssh,
)


def joined(result) -> str:
    return "\n".join(result.output)


def connect(net, source: str, destination: str, port: int, protocol: str = "TCP"):
    return run_connection_test(
        net.build(), net.device_id(source), destination, port, protocol
    )


class TestListeningPorts:
    def test_an_open_port_completes_the_handshake(self):
        result = connect(campus_network(), "PC-01", "10.0.2.10", 80)
        assert result.reachable
        assert result.outcome == "open"

    def test_a_closed_port_is_refused_not_silent(self):
        result = connect(campus_network(), "PC-01", "10.0.2.10", 22)
        assert not result.reachable
        assert result.outcome == "refused"
        assert result.blocked_at == "WEB-01"

    def test_a_disabled_service_closes_its_port(self):
        net = campus_network()
        web = next(d for d in net.devices if d.name == "WEB-01")
        web.config.services = [http(enabled=False), https()]

        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "refused"
        assert connect(net, "PC-01", "10.0.2.10", 443).outcome == "open"

    def test_enabling_a_service_opens_it(self):
        net = campus_network()
        web = next(d for d in net.devices if d.name == "WEB-01")
        web.config.services = [http(), https(), ssh()]
        assert connect(net, "PC-01", "10.0.2.10", 22).outcome == "open"

    def test_netstat_lists_what_is_listening(self):
        net = campus_network()
        result = run_command(net.build(), net.device_id("WEB-01"), "netstat")
        text = joined(result)
        assert "80" in text and "HTTP" in text
        assert "443" in text

    def test_netstat_on_a_device_with_no_services_says_so(self):
        net = campus_network()
        result = run_command(net.build(), net.device_id("PC-01"), "netstat")
        assert "Nothing is listening" in joined(result)

    def test_the_path_is_recorded_and_stops_at_the_destination(self):
        result = connect(campus_network(), "PC-01", "10.0.2.10", 80)
        assert result.path == [
            "PC-01",
            "Switch-01",
            "Firewall-01",
            "Router-01",
            "Switch-02",
            "WEB-01",
        ]


class TestFirewallRules:
    def test_a_deny_rule_makes_the_port_look_filtered(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        result = connect(net, "PC-01", "10.0.2.10", 80)
        assert not result.reachable
        assert result.outcome == "filtered"
        assert result.blocked_at == "Firewall-01"
        assert "rule 1" in (result.blocked_reason or "")

    def test_a_deny_rule_only_affects_the_port_it_names(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        assert connect(net, "PC-01", "10.0.2.10", 443).outcome == "open"

    def test_dns_still_works_while_http_is_blocked(self):
        # "DNS resolves but the site will not load" — the scenario in the brief.
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        lookup = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert lookup.success
        assert connect(net, "PC-01", "web.netquest.local", 80).outcome == "filtered"

    def test_a_default_deny_policy_blocks_everything_unmatched(self):
        net = campus_network(default_policy="deny")
        result = connect(net, "PC-01", "10.0.2.10", 80)
        assert result.outcome == "filtered"
        assert "default policy is deny" in (result.blocked_reason or "")

    def test_an_allow_rule_punches_through_a_default_deny(self):
        net = campus_network(
            firewall_rules=[allow("tcp", 80), allow("udp", 53)],
            default_policy="deny",
        )
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "open"
        assert connect(net, "PC-01", "10.0.2.10", 443).outcome == "filtered"

    def test_the_first_matching_rule_wins(self):
        # A broad deny above a specific allow defeats it — the classic mistake.
        net = campus_network(
            firewall_rules=[deny("tcp"), allow("tcp", 80)], default_policy="allow"
        )
        result = connect(net, "PC-01", "10.0.2.10", 80)
        assert result.outcome == "filtered"
        assert "rule 1" in (result.blocked_reason or "")

    def test_ordering_the_rules_correctly_fixes_it(self):
        net = campus_network(
            firewall_rules=[allow("tcp", 80), deny("tcp")], default_policy="allow"
        )
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "open"
        assert connect(net, "PC-01", "10.0.2.10", 443).outcome == "filtered"

    def test_rules_can_be_scoped_to_a_source(self):
        net = campus_network(
            firewall_rules=[
                FirewallRuleSchema(
                    action="deny", protocol="tcp", port=80, source="10.0.1.10/32"
                )
            ]
        )
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "filtered"
        # PC-02 is not covered by the rule.
        assert connect(net, "PC-02", "10.0.2.10", 80).outcome == "open"

    def test_rules_can_be_scoped_to_a_destination_network(self):
        net = campus_network(
            firewall_rules=[
                FirewallRuleSchema(
                    action="deny", protocol="any", destination="10.0.2.0/24"
                )
            ]
        )
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "filtered"

    def test_icmp_can_be_blocked_on_its_own(self):
        net = campus_network(firewall_rules=[deny("icmp")])
        ping = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.2.10 -n 1")
        assert not ping.success
        # HTTP is untouched.
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "open"

    def test_arp_is_never_filtered(self):
        # Filtering ARP would make the firewall look like a cut cable, which
        # teaches nothing, so it always passes.
        net = campus_network(default_policy="deny")
        result = run_command(net.build(), net.device_id("PC-01"), "ping 10.0.1.11 -n 1")
        assert result.success, "PC-01 and PC-02 are on the same side of the firewall"


class TestFirewallVisibility:
    def test_show_access_list_names_every_rule(self):
        net = campus_network(
            firewall_rules=[deny("tcp", 80, description="block plain web")]
        )
        result = run_command(net.build(), net.device_id("Firewall-01"), "show access-list")
        text = joined(result)
        assert "deny" in text
        assert "80/tcp (HTTP)" in text
        assert "block plain web" in text
        assert "Default policy: allow" in text

    def test_hit_counters_survive_between_commands(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        topology = net.build()
        blocked = run_connection_test(
            topology, net.device_id("PC-01"), "10.0.2.10", 80, "TCP"
        )
        assert blocked.outcome == "filtered"

        firewall_id = net.device_id("Firewall-01")
        for device in topology.devices:
            if device.id == firewall_id:
                device.runtime.firewall_hits = dict(
                    blocked.device_state[firewall_id].firewall_hits
                )

        shown = run_command(topology, firewall_id, "show access-list")
        assert "  1 " in joined(shown)
        assert blocked.device_state[firewall_id].firewall_hits.get("0", 0) >= 1

    def test_counters_can_be_cleared(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        topology = net.build()
        firewall_id = net.device_id("Firewall-01")
        for device in topology.devices:
            if device.id == firewall_id:
                device.runtime.firewall_hits = {"0": 7}
        result = run_command(topology, firewall_id, "clear counters")
        assert "7" in joined(result)


class TestUdpServices:
    def test_a_udp_port_nobody_listens_on_returns_port_unreachable(self):
        net = campus_network()
        result = connect(net, "PC-01", "10.0.2.10", 9999, "UDP")
        assert not result.reachable
        assert result.outcome == "refused"

    def test_blocking_udp_53_breaks_name_resolution_only(self):
        net = campus_network(firewall_rules=[deny("udp", 53)])
        lookup = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert not lookup.success
        # The web server itself is still perfectly reachable by address.
        assert connect(net, "PC-01", "10.0.2.10", 80).outcome == "open"


class TestConnectCommand:
    def test_connect_reports_an_open_port(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "connect web.netquest.local 80"
        )
        assert result.success
        assert "open" in joined(result)
        assert "Path:" in joined(result)

    def test_connect_accepts_a_service_name(self):
        net = campus_network()
        result = run_command(net.build(), net.device_id("PC-01"), "connect 10.0.2.10 http")
        assert result.success

    def test_connect_reports_where_traffic_stopped(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        result = run_command(net.build(), net.device_id("PC-01"), "connect 10.0.2.10 80")
        assert not result.success
        assert "Stopped at: Firewall-01" in joined(result)

    def test_curl_reports_reachability_without_inventing_a_page(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "curl http://web.netquest.local"
        )
        assert result.success
        text = joined(result)
        assert "Connected to" in text
        assert "simulates the connection" in text

    def test_curl_fails_honestly_when_blocked(self):
        net = campus_network(firewall_rules=[deny("tcp", 80)])
        result = run_command(
            net.build(), net.device_id("PC-01"), "curl http://web.netquest.local"
        )
        assert not result.success
        assert "Firewall-01" in joined(result)


class TestConnectionEndpointEdges:
    def test_a_switch_cannot_originate_a_connection(self):
        net = campus_network()
        result = run_connection_test(
            net.build(), net.device_id("Switch-01"), "10.0.2.10", 80
        )
        assert not result.reachable
        assert "have to start" in result.detail

    def test_an_unknown_device_is_reported_not_raised(self):
        net = campus_network()
        result = run_connection_test(net.build(), "nope", "10.0.2.10", 80)
        assert not result.reachable

    def test_a_host_with_no_address_cannot_connect(self):
        net = campus_network()
        net.devices[0].interfaces[0].ipv4 = None
        result = connect(net, "PC-01", "10.0.2.10", 80)
        assert result.outcome == "no-source-address"

    def test_an_unresolvable_name_is_a_dns_failure_not_a_dead_port(self):
        net = campus_network()
        result = connect(net, "PC-01", "ghost.netquest.local", 80)
        assert result.outcome == "dns-failure"


class TestServicesAcrossASwitchOnly:
    def test_two_hosts_on_one_switch_reach_each_others_services(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.5.10")
        net.web_server("WEB-01", "192.168.5.20")
        net.switch("Switch-01", ports=4)
        net.link("PC-01", 0, "Switch-01", 0)
        net.link("WEB-01", 0, "Switch-01", 1)

        assert connect(net, "PC-01", "192.168.5.20", 80).outcome == "open"
        assert connect(net, "PC-01", "192.168.5.20", 22).outcome == "refused"

    def test_a_disabled_switch_port_isolates_the_service(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.5.10")
        net.web_server("WEB-01", "192.168.5.20")
        switch = net.switch("Switch-01", ports=4)
        net.link("PC-01", 0, "Switch-01", 0)
        net.link("WEB-01", 0, "Switch-01", 1)
        switch.interfaces[1].enabled = False

        result = connect(net, "PC-01", "192.168.5.20", 80)
        assert not result.reachable
