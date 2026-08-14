"""The services and security missions must be broken on arrival and fixable.

Each test applies the fix a learner would apply, through the same fields the
config panel edits, and checks the objectives then pass.
"""

import pytest

from app.challenges import loader, validator
from app.schemas.challenge import ChallengeSchema
from app.schemas.topology import DhcpPoolSchema, NatSchema, TopologySchema, VpnSchema
from app.simulation.runner import run_command
from builders import DEFAULT_MASK, apply_state

ALL = loader.reload()

NEW_IDS = [
    "names-not-numbers",
    "the-stale-record",
    "the-broken-alias",
    "addresses-on-demand",
    "the-wrong-pool",
    "the-closed-port",
    "dns-works-web-does-not",
    "rules-in-the-wrong-order",
    "nobody-answers-a-private-address",
    "through-the-tunnel",
]


def challenge(challenge_id: str) -> ChallengeSchema:
    assert challenge_id in ALL, f"missing challenge file: {challenge_id}"
    return ALL[challenge_id]


def check(challenge_id: str, topology: TopologySchema):
    return validator.validate(challenge(challenge_id), topology)


def start(challenge_id: str) -> TopologySchema:
    topology = challenge(challenge_id).topology
    assert topology is not None, f"{challenge_id} ships no topology"
    return topology.model_copy(deep=True)


def device(topology: TopologySchema, name: str):
    return next(d for d in topology.devices if d.name == name)


def unmet(result) -> list[str]:
    return [f"{o.description} — {o.detail}" for o in result.objectives if not o.complete]


class TestTheFilesThemselves:
    def test_all_ten_are_present(self):
        for challenge_id in NEW_IDS:
            assert challenge_id in ALL

    def test_the_library_has_grown(self):
        assert len(ALL) >= 21

    @pytest.mark.parametrize("challenge_id", NEW_IDS)
    def test_each_is_well_formed(self, challenge_id):
        c = ALL[challenge_id]
        assert c.brief and c.description
        assert c.hints, "every mission needs a way out"
        assert c.explanation, "the lesson has to be spelled out after solving"
        assert c.objectives
        assert c.topology is not None

    @pytest.mark.parametrize("challenge_id", NEW_IDS)
    def test_each_starts_unsolved(self, challenge_id):
        """The whole point: none may pass before the learner does anything."""
        assert not check(challenge_id, start(challenge_id)).complete


class TestDnsMissions:
    def test_names_not_numbers(self):
        topology = start("names-not-numbers")
        # Addresses already work, which is the clue.
        assert run_command(topology, device(topology, "PC-01").id, "ping 10.0.2.10 -n 1").success

        for name in ("PC-01", "PC-02"):
            device(topology, name).config.dns_server = "10.0.2.53"
        result = check("names-not-numbers", topology)
        assert result.complete, unmet(result)

    def test_the_stale_record(self):
        topology = start("the-stale-record")
        dns = device(topology, "DNS-01")
        record = next(
            r for r in dns.config.dns_records if r.name == "web.netquest.local"
        )
        assert record.value == "10.0.2.99", "the mission should ship a wrong answer"

        record.value = "10.0.2.10"
        result = check("the-stale-record", topology)
        assert result.complete, unmet(result)

    def test_the_broken_alias(self):
        topology = start("the-broken-alias")
        dns = device(topology, "DNS-01")
        alias = next(r for r in dns.config.dns_records if r.type == "CNAME")
        assert alias.value == "webserver.netquest.local"

        alias.value = "web.netquest.local"
        result = check("the-broken-alias", topology)
        assert result.complete, unmet(result)


class TestDhcpMissions:
    def test_addresses_on_demand(self):
        topology = start("addresses-on-demand")
        server = device(topology, "DHCP-01")
        assert server.config.dhcp_pool is None

        server.config.dhcp_pool = DhcpPoolSchema(
            start="10.0.1.100",
            end="10.0.1.110",
            netmask=DEFAULT_MASK,
            gateway="10.0.1.1",
            dns="10.0.2.53",
        )
        client = device(topology, "PC-02")
        client.config.dhcp_client = True

        # The learner then runs 'dhcp renew' in the terminal.
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))
        assert client.interfaces[0].ipv4 == "10.0.1.100"

        result = check("addresses-on-demand", topology)
        assert result.complete, unmet(result)

    def test_the_wrong_pool(self):
        topology = start("the-wrong-pool")
        client = device(topology, "PC-02")

        # As shipped, renewing gives a useless address.
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))
        assert client.interfaces[0].ipv4 == "192.168.77.100"
        assert not check("the-wrong-pool", topology).complete

        server = device(topology, "DHCP-01")
        server.config.dhcp_pool = DhcpPoolSchema(
            start="10.0.1.100",
            end="10.0.1.110",
            netmask=DEFAULT_MASK,
            gateway="10.0.1.1",
            dns="10.0.2.53",
        )
        apply_state(topology, run_command(topology, client.id, "dhcp release"))
        apply_state(topology, run_command(topology, client.id, "dhcp renew"))

        result = check("the-wrong-pool", topology)
        assert result.complete, unmet(result)


class TestSecurityMissions:
    def test_the_closed_port(self):
        topology = start("the-closed-port")
        web = device(topology, "WEB-01")
        https = next(s for s in web.config.services if s.port == 443)
        assert not https.enabled

        https.enabled = True
        result = check("the-closed-port", topology)
        assert result.complete, unmet(result)

    def test_dns_works_web_does_not(self):
        topology = start("dns-works-web-does-not")
        firewall = device(topology, "Firewall-01")
        assert firewall.config.firewall_rules

        firewall.config.firewall_rules = []
        result = check("dns-works-web-does-not", topology)
        assert result.complete, unmet(result)

    def test_rules_in_the_wrong_order(self):
        topology = start("rules-in-the-wrong-order")
        firewall = device(topology, "Firewall-01")
        rules = firewall.config.firewall_rules
        assert rules[0].action == "deny" and rules[0].port is None

        # Move the specific allow above the broad deny.
        broad_deny = rules.pop(0)
        rules.append(broad_deny)
        firewall.config.firewall_rules = rules

        result = check("rules-in-the-wrong-order", topology)
        assert result.complete, unmet(result)

    def test_nobody_answers_a_private_address(self):
        topology = start("nobody-answers-a-private-address")
        router = device(topology, "Router-01")
        assert router.config.nat is None or not router.config.nat.enabled

        router.config.nat = NatSchema(
            enabled=True, outside_interface_id=router.interfaces[1].id
        )
        result = check("nobody-answers-a-private-address", topology)
        assert result.complete, unmet(result)

    def test_through_the_tunnel(self):
        topology = start("through-the-tunnel")
        laptop = device(topology, "LAPTOP-01")
        firewall = device(topology, "Firewall-01")
        assert firewall.config.firewall_rules, "the SSH block must stay"

        laptop.config.vpn = VpnSchema(
            server="10.8.0.10",
            remote_network="10.8.0.0",
            remote_netmask=DEFAULT_MASK,
            tunnel_ip="10.8.0.200",
        )
        result = check("through-the-tunnel", topology)
        assert result.complete, unmet(result)

        # And the firewall rule is still doing its job for direct traffic.
        assert firewall.config.firewall_rules[0].action == "deny"


class TestObjectiveTypes:
    def test_service_blocked_is_satisfied_by_a_closed_port(self):
        from app.schemas.challenge import ObjectiveSchema, ObjectiveType

        topology = start("the-closed-port")
        fake = ChallengeSchema(
            id="t",
            name="t",
            category="security",
            description="d",
            brief="b",
            objectives=[
                ObjectiveSchema(
                    type=ObjectiveType.SERVICE_BLOCKED,
                    source="PC-01",
                    destination="10.0.2.10",
                    port=443,
                    protocol="TCP",
                )
            ],
        )
        assert validator.validate(fake, topology).complete

        device(topology, "WEB-01").config.services[1].enabled = True
        assert not validator.validate(fake, topology).complete

    def test_dhcp_assigns_needs_the_client_flag(self):
        from app.schemas.challenge import ObjectiveSchema, ObjectiveType

        topology = start("addresses-on-demand")
        fake = ChallengeSchema(
            id="t",
            name="t",
            category="services",
            description="d",
            brief="b",
            objectives=[
                ObjectiveSchema(type=ObjectiveType.DHCP_ASSIGNS, device="PC-01")
            ],
        )
        # PC-01 is statically addressed, so this must not pass.
        assert not validator.validate(fake, topology).complete
