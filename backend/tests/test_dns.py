"""DNS: zone resolution, real queries over the wire, and the client tools."""

from app.simulation.dns.records import (
    DnsRecord,
    DnsRecordType,
    DnsStatus,
    DnsZone,
    normalize_name,
)
from app.simulation.runner import run_command
from builders import a_record, apply_state, campus_network, cname, dns_service


def joined(result) -> str:
    return "\n".join(result.output)


def zone(*records: DnsRecord) -> DnsZone:
    return DnsZone(records=list(records))


class TestZoneResolution:
    def test_a_record_resolves(self):
        z = zone(DnsRecord("web.local", DnsRecordType.A, "10.0.0.5"))
        result = z.resolve("web.local")
        assert result.ok
        assert result.address == "10.0.0.5"

    def test_names_are_case_insensitive_and_dot_tolerant(self):
        z = zone(DnsRecord("Web.Local", DnsRecordType.A, "10.0.0.5"))
        assert z.resolve("WEB.local.").address == "10.0.0.5"
        assert normalize_name("  Web.Local.  ") == "web.local"

    def test_cname_is_followed_to_the_address(self):
        z = zone(
            DnsRecord("www.local", DnsRecordType.CNAME, "web.local"),
            DnsRecord("web.local", DnsRecordType.A, "10.0.0.5"),
        )
        result = z.resolve("www.local")
        assert result.ok
        assert result.address == "10.0.0.5"
        # The trail is kept so the learner can see the indirection.
        assert [r.type for r in result.chain] == [DnsRecordType.CNAME, DnsRecordType.A]

    def test_a_cname_pointing_nowhere_is_nxdomain(self):
        z = zone(DnsRecord("www.local", DnsRecordType.CNAME, "missing.local"))
        result = z.resolve("www.local")
        assert result.status is DnsStatus.NXDOMAIN
        assert "missing.local" in result.detail

    def test_a_cname_loop_is_servfail_not_a_hang(self):
        z = zone(
            DnsRecord("a.local", DnsRecordType.CNAME, "b.local"),
            DnsRecord("b.local", DnsRecordType.CNAME, "a.local"),
        )
        result = z.resolve("a.local")
        assert result.status is DnsStatus.SERVFAIL
        assert "loop" in result.detail

    def test_an_a_record_holding_rubbish_is_servfail(self):
        z = zone(DnsRecord("web.local", DnsRecordType.A, "not-an-address"))
        assert z.resolve("web.local").status is DnsStatus.SERVFAIL

    def test_unknown_name_is_nxdomain(self):
        assert zone().resolve("nothing.local").status is DnsStatus.NXDOMAIN

    def test_mx_records_come_back_in_priority_order(self):
        z = zone(
            DnsRecord("local", DnsRecordType.MX, "backup.local", priority=20),
            DnsRecord("local", DnsRecordType.MX, "primary.local", priority=10),
        )
        result = z.resolve("local", DnsRecordType.MX)
        assert result.ok
        assert [r.value for r in result.answers] == ["primary.local", "backup.local"]

    def test_an_a_lookup_does_not_answer_from_an_mx_record(self):
        z = zone(DnsRecord("local", DnsRecordType.MX, "mail.local"))
        assert z.resolve("local", DnsRecordType.A).status is DnsStatus.NXDOMAIN


class TestQueriesOverTheNetwork:
    def test_nslookup_resolves_through_the_real_server(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert result.success
        assert "10.0.2.10" in joined(result)
        # It really was a UDP/53 exchange, not a lookup in a local table.
        assert any(e.type == "dns_query" for e in result.events)
        assert any(p.dst_port == 53 for p in result.packets)

    def test_nslookup_follows_a_cname(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup www.netquest.local"
        )
        assert result.success
        assert "canonical name" in joined(result)
        assert "10.0.2.10" in joined(result)

    def test_an_unknown_name_reports_nxdomain(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup nope.netquest.local"
        )
        assert not result.success
        assert "NXDOMAIN" in joined(result)

    def test_a_host_with_no_dns_server_says_so(self):
        net = campus_network()
        net.devices[0].config.dns_server = None
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert not result.success
        assert "No DNS server is configured" in joined(result)

    def test_an_unreachable_dns_server_is_a_timeout_not_nxdomain(self):
        net = campus_network()
        net.devices[0].config.dns_server = "10.0.2.99"  # nobody holds this
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert not result.success
        assert "no response" in joined(result)

    def test_disabling_the_dns_service_closes_the_port(self):
        net = campus_network()
        dns = next(d for d in net.devices if d.name == "DNS-01")
        dns.config.services = [dns_service(enabled=False)]
        result = run_command(
            net.build(), net.device_id("PC-01"), "nslookup web.netquest.local"
        )
        assert not result.success

    def test_dig_shows_the_full_chain(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "dig www.netquest.local"
        )
        assert result.success
        text = joined(result)
        assert "ANSWER SECTION" in text
        assert "CNAME" in text
        assert "STATUS: NOERROR" in text

    def test_dig_can_ask_for_mx(self):
        net = campus_network()
        result = run_command(net.build(), net.device_id("PC-01"), "dig netquest.local MX")
        assert result.success
        assert "MX" in joined(result)


class TestDnsAffectsEverythingElse:
    def test_ping_accepts_a_hostname(self):
        net = campus_network()
        result = run_command(
            net.build(), net.device_id("PC-01"), "ping web.netquest.local -n 1"
        )
        assert result.success
        assert "web.netquest.local [10.0.2.10]" in joined(result)

    def test_a_wrong_a_record_sends_the_ping_to_the_wrong_place(self):
        # The classic fault: DNS answers, but with the wrong address.
        net = campus_network()
        dns = next(d for d in net.devices if d.name == "DNS-01")
        dns.config.dns_records = [
            a_record("web.netquest.local", "10.0.2.99"),
            cname("www.netquest.local", "web.netquest.local"),
        ]
        result = run_command(
            net.build(), net.device_id("PC-01"), "ping web.netquest.local -n 1"
        )
        assert not result.success
        # DNS itself worked — the address it handed back simply has no host.
        assert "10.0.2.99" in joined(result)
        assert any(e.type == "dns_response" for e in result.events)

    def test_a_missing_record_fails_before_any_packet_is_sent(self):
        net = campus_network()
        dns = next(d for d in net.devices if d.name == "DNS-01")
        dns.config.dns_records = []
        result = run_command(
            net.build(), net.device_id("PC-01"), "ping web.netquest.local -n 1"
        )
        assert not result.success
        assert "NXDOMAIN" in joined(result)
        assert not any(e.type == "icmp_request" for e in result.events)

    def test_the_cache_is_remembered_between_commands(self):
        net = campus_network()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        apply_state(topology, run_command(topology, pc1, "nslookup web.netquest.local"))

        second = run_command(topology, pc1, "ping web.netquest.local -n 1")
        assert second.success
        assert any(e.type == "dns_cache_hit" for e in second.events)
        assert not any(e.type == "dns_query" for e in second.events)

    def test_the_cache_is_visible_to_the_learner(self):
        net = campus_network()
        topology = net.build()
        pc1 = net.device_id("PC-01")
        apply_state(topology, run_command(topology, pc1, "nslookup web.netquest.local"))

        shown = run_command(topology, pc1, "dns-cache")
        assert "web.netquest.local" in joined(shown)
