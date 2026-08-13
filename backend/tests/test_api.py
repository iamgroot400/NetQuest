"""HTTP surface."""

from fastapi.testclient import TestClient

from app.main import app
from builders import two_pc_lan

client = TestClient(app)


class TestMeta:
    def test_health(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_openapi_document_is_generated(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/v1/simulate/command" in response.json()["paths"]


class TestSimulateCommand:
    def test_a_successful_ping_over_http(self):
        net = two_pc_lan()
        response = client.post(
            "/api/v1/simulate/command",
            json={
                "topology": net.build().model_dump(mode="json"),
                "device_id": net.device_id("PC-01"),
                "command": "ping 192.168.1.20 -n 1",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"]
        assert any("Reply from 192.168.1.20" in line for line in body["output"])
        assert body["events"]
        assert body["packets"]
        assert body["device_state"][net.device_id("Switch-01")]["mac_table"]

    def test_an_unknown_device_is_reported_not_crashed(self):
        net = two_pc_lan()
        response = client.post(
            "/api/v1/simulate/command",
            json={
                "topology": net.build().model_dump(mode="json"),
                "device_id": "does-not-exist",
                "command": "ipconfig",
            },
        )
        assert response.status_code == 200
        assert not response.json()["success"]

    def test_a_malformed_request_is_rejected(self):
        assert client.post("/api/v1/simulate/command", json={"nope": 1}).status_code == 422


class TestTopologyValidation:
    def test_a_clean_topology_validates(self):
        response = client.post(
            "/api/v1/topology/validate",
            json=two_pc_lan().build().model_dump(mode="json"),
        )
        assert response.status_code == 200
        assert response.json()["valid"]

    def test_a_bad_address_is_reported(self):
        net = two_pc_lan()
        net.devices[0].interfaces[0].ipv4 = "300.1.1.1"
        response = client.post(
            "/api/v1/topology/validate", json=net.build().model_dump(mode="json")
        )
        assert not response.json()["valid"]


class TestCommandReference:
    def test_every_device_type_lists_its_commands(self):
        body = client.get("/api/v1/commands").json()
        assert {"pc", "switch", "router", "server"} <= set(body)
        assert any(c["name"] == "show mac-address-table" for c in body["switch"])
        assert any(c["name"] == "ping" for c in body["pc"])


class TestChallengeEndpoints:
    def test_listing_returns_challenges_in_play_order(self):
        body = client.get("/api/v1/challenges").json()
        assert len(body) >= 10
        levels = [c["level"] for c in body]
        assert levels == sorted(levels)

    def test_fetching_one_challenge(self):
        body = client.get("/api/v1/challenges/first-contact").json()
        assert body["name"] == "First Contact"
        assert body["objectives"]

    def test_unknown_challenge_is_a_404(self):
        assert client.get("/api/v1/challenges/nope").status_code == 404

    def test_validating_an_unsolved_challenge(self):
        net = two_pc_lan()
        response = client.post(
            "/api/v1/challenges/first-contact/validate",
            json={"topology": net.build().model_dump(mode="json")},
        )
        assert response.status_code == 200
        body = response.json()
        assert not body["complete"]
        assert body["xp"] == 0
        assert len(body["objectives"]) == 5

    def test_validating_a_solved_challenge_awards_xp(self):
        from builders import TopologyBuilder

        net = TopologyBuilder()
        net.pc("PC-01", "192.168.1.10")
        net.pc("PC-02", "192.168.1.20")
        net.link("PC-01", 0, "PC-02", 0)
        response = client.post(
            "/api/v1/challenges/first-contact/validate",
            json={"topology": net.build().model_dump(mode="json")},
        )
        body = response.json()
        assert body["complete"]
        assert body["xp"] == 100
