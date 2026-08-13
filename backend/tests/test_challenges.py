"""The shipped challenges must be broken when handed out and pass once fixed.

Every mission is validated by running the real engine, so these tests are also
a regression net for the simulator itself.
"""

import pytest

from app.challenges import loader, validator
from app.schemas.challenge import ChallengeSchema
from app.schemas.topology import StaticRouteSchema, TopologySchema
from builders import DEFAULT_MASK, TopologyBuilder

ALL = loader.reload()


def challenge(challenge_id: str) -> ChallengeSchema:
    assert challenge_id in ALL, f"missing challenge file: {challenge_id}"
    return ALL[challenge_id]


def check(challenge_id: str, topology: TopologySchema):
    return validator.validate(challenge(challenge_id), topology)


def starting_topology(challenge_id: str) -> TopologySchema:
    topology = challenge(challenge_id).topology
    assert topology is not None, f"{challenge_id} has no preset topology"
    return topology.model_copy(deep=True)


def device(topology: TopologySchema, name: str):
    return next(d for d in topology.devices if d.name == name)


def unmet(result) -> list[str]:
    return [o.description for o in result.objectives if not o.complete]


class TestChallengeFiles:
    def test_files_are_discovered(self):
        assert len(ALL) >= 10

    @pytest.mark.parametrize("challenge_id", sorted(ALL))
    def test_every_challenge_is_well_formed(self, challenge_id):
        c = ALL[challenge_id]
        assert c.name and c.description and c.brief
        assert c.objectives, "a challenge with no objectives can never be completed"
        assert c.xp > 0
        assert 1 <= c.difficulty <= 5
        assert c.hints, "learners need somewhere to turn"

    @pytest.mark.parametrize("challenge_id", sorted(ALL))
    def test_prerequisites_exist(self, challenge_id):
        for required in ALL[challenge_id].requires:
            assert required in ALL, f"{challenge_id} requires unknown '{required}'"

    def test_an_empty_canvas_completes_nothing(self):
        empty = TopologySchema()
        for challenge_id in ALL:
            assert not check(challenge_id, empty).complete


class TestBuildFromScratch:
    def test_first_contact(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10")
        net.pc("PC-02", "192.168.1.20")

        result = check("first-contact", net.build())
        assert not result.complete, "no cable yet"

        net.link("PC-01", 0, "PC-02", 0)
        result = check("first-contact", net.build())
        assert result.complete, unmet(result)
        assert result.xp == 100

    def test_connect_the_office(self):
        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10")
        net.pc("PC-02", "192.168.1.20")
        net.pc("PC-03", "192.168.1.30")
        net.switch("Switch-01")
        net.link("PC-01", 0, "Switch-01", 0)
        net.link("PC-02", 0, "Switch-01", 1)

        result = check("connect-the-office", net.build())
        assert not result.complete, "PC-03 is not cabled yet"

        net.link("PC-03", 0, "Switch-01", 2)
        result = check("connect-the-office", net.build())
        assert result.complete, unmet(result)

    def test_two_switch_lan(self):
        net = TopologyBuilder()
        for index in range(1, 5):
            net.pc(f"PC-0{index}", f"10.0.0.{index}")
        net.switch("Switch-01")
        net.switch("Switch-02")
        net.link("PC-01", 0, "Switch-01", 0)
        net.link("PC-02", 0, "Switch-01", 1)
        net.link("PC-03", 0, "Switch-02", 0)
        net.link("PC-04", 0, "Switch-02", 1)

        result = check("two-switch-lan", net.build())
        assert not result.complete, "the two switches are still islands"

        net.link("Switch-01", 7, "Switch-02", 7)
        result = check("two-switch-lan", net.build())
        assert result.complete, unmet(result)

    def test_build_the_router(self):
        net = TopologyBuilder()
        net.pc("PC-01", "172.16.1.10", gateway="172.16.1.1")
        net.switch("Switch-01")
        net.router("Router-01", [("172.16.1.1", DEFAULT_MASK), ("172.16.2.1", DEFAULT_MASK)])
        net.switch("Switch-02")
        net.server("Server-01", "172.16.2.50")
        net.link("PC-01", 0, "Switch-01", 0)
        net.link("Switch-01", 1, "Router-01", 0)
        net.link("Router-01", 1, "Switch-02", 0)
        net.link("Switch-02", 1, "Server-01", 0)

        result = check("build-the-router", net.build())
        assert not result.complete, "Server-01 still has no gateway"

        device(net.build(), "Server-01")  # sanity: the name matches the objective
        net.devices[4].config.gateway = "172.16.2.1"
        result = check("build-the-router", net.build())
        assert result.complete, unmet(result)


class TestPresetScenarios:
    def test_learning_switch_ships_already_working(self):
        # A teaching mission, not a repair job: the objectives pass immediately
        # and the lesson is in watching the MAC table fill.
        result = check("learning-switch", starting_topology("learning-switch"))
        assert result.complete, unmet(result)

    def test_the_mask_matters(self):
        topology = starting_topology("the-mask-matters")
        assert not check("the-mask-matters", topology).complete

        device(topology, "PC-02").interfaces[0].netmask = "255.255.255.0"
        result = check("the-mask-matters", topology)
        assert result.complete, unmet(result)

    def test_crossing_the_line(self):
        topology = starting_topology("crossing-the-line")
        assert not check("crossing-the-line", topology).complete

        device(topology, "PC-01").config.gateway = "192.168.10.1"
        device(topology, "PC-02").config.gateway = "192.168.10.1"
        partial = check("crossing-the-line", topology)
        assert not partial.complete, "the server still cannot reply"

        device(topology, "Server-01").config.gateway = "192.168.20.1"
        result = check("crossing-the-line", topology)
        assert result.complete, unmet(result)

    def test_the_missing_route(self):
        topology = starting_topology("the-missing-route")
        assert not check("the-missing-route", topology).complete

        device(topology, "Router-01").config.static_routes = [
            StaticRouteSchema(
                destination="192.168.20.0", netmask=DEFAULT_MASK, gateway="10.0.0.2"
            )
        ]
        one_way = check("the-missing-route", topology)
        assert not one_way.complete, "packets still have no way home"

        device(topology, "Router-02").config.static_routes = [
            StaticRouteSchema(
                destination="192.168.10.0", netmask=DEFAULT_MASK, gateway="10.0.0.1"
            )
        ]
        result = check("the-missing-route", topology)
        assert result.complete, unmet(result)

    def test_the_severed_cable(self):
        topology = starting_topology("the-severed-cable")
        assert not check("the-severed-cable", topology).complete
        assert any(link.status == "down" for link in topology.links)

        for link in topology.links:
            link.status = "up"
        result = check("the-severed-cable", topology)
        assert result.complete, unmet(result)

    def test_the_silent_server(self):
        topology = starting_topology("the-silent-server")
        assert not check("the-silent-server", topology).complete

        device(topology, "Server-01").config.gateway = "192.168.20.1"
        result = check("the-silent-server", topology)
        assert result.complete, unmet(result)

    def test_the_wrong_turn(self):
        topology = starting_topology("the-wrong-turn")
        assert not check("the-wrong-turn", topology).complete

        # The local network was never the problem.
        from app.simulation.runner import run_command

        local = run_command(topology, device(topology, "PC-01").id, "ping 192.168.10.21 -n 1")
        assert local.success

        device(topology, "PC-01").config.gateway = "192.168.10.1"
        result = check("the-wrong-turn", topology)
        assert result.complete, unmet(result)


class TestObjectiveTypes:
    def test_ping_fails_objective_is_satisfied_by_a_broken_link(self):
        from app.schemas.challenge import ObjectiveSchema, ObjectiveType

        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10")
        net.pc("PC-02", "192.168.1.20")
        objective = ObjectiveSchema(
            type=ObjectiveType.PING_FAILS, source="PC-01", destination="PC-02"
        )
        fake = ChallengeSchema(
            id="t", name="t", category="beginner", description="d", brief="b",
            objectives=[objective],
        )

        assert validator.validate(fake, net.build()).complete, "no cable, so it must fail"

        net.link("PC-01", 0, "PC-02", 0)
        assert not validator.validate(fake, net.build()).complete
