"""Challenge file format and validation results.

A challenge is pure data. Contributors add a JSON file under `challenges/` and
the simulator picks it up — no core code changes. See docs/ADDING-CHALLENGES.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .topology import DeviceType, TopologySchema


class ObjectiveType(str, Enum):
    DEVICE_EXISTS = "device_exists"
    LINK_EXISTS = "link_exists"
    INTERFACE_CONFIGURED = "interface_configured"
    IN_SUBNET = "in_subnet"
    PING_SUCCEEDS = "ping_succeeds"
    PING_FAILS = "ping_fails"
    #: A name resolves through the simulated DNS, optionally to a given address.
    DNS_RESOLVES = "dns_resolves"
    #: A TCP/UDP port genuinely accepts a connection.
    SERVICE_REACHABLE = "service_reachable"
    #: …and the same test proving something is correctly *not* reachable.
    SERVICE_BLOCKED = "service_blocked"
    #: A device is listening on a port.
    SERVICE_ENABLED = "service_enabled"
    #: A client holds an address it was given by DHCP.
    DHCP_ASSIGNS = "dhcp_assigns"


class ObjectiveSchema(BaseModel):
    type: ObjectiveType
    #: Optional override; a readable description is generated when absent.
    description: str | None = None

    # device_exists
    device_type: DeviceType | None = None
    count: int | None = None

    # link_exists — device names
    a: str | None = None
    b: str | None = None

    # interface_configured / in_subnet — device name plus expected values
    device: str | None = None
    interface: str | None = None
    ipv4: str | None = None
    netmask: str | None = None
    gateway: str | None = None
    subnet: str | None = None

    # ping_succeeds / ping_fails — device names; destination may be an address
    source: str | None = None
    destination: str | None = None

    # dns_resolves — which host asks, for what, and optionally what it must get
    name: str | None = None
    expects: str | None = None

    # service_reachable / service_blocked / service_enabled
    port: int | None = None
    protocol: str = "TCP"


class ChallengeCategory(str, Enum):
    BEGINNER = "beginner"
    SWITCHING = "switching"
    ROUTING = "routing"
    TROUBLESHOOTING = "troubleshooting"
    #: DNS, DHCP and the services that run on top of a working network.
    SERVICES = "services"
    #: Firewalls, NAT and tunnelling.
    SECURITY = "security"


class ChallengeSchema(BaseModel):
    id: str
    name: str
    category: ChallengeCategory
    #: 1-5 stars.
    difficulty: int = 1
    xp: int = 100
    #: Progression level this challenge belongs to.
    level: int = 1
    description: str = ""
    #: Longer scenario text shown in the mission briefing.
    brief: str = ""
    hints: list[str] = Field(default_factory=list)
    #: Shown once the mission is solved: what happened, why, and what it teaches.
    explanation: str = ""
    #: Starting topology. Null means "start from an empty canvas".
    topology: TopologySchema | None = None
    objectives: list[ObjectiveSchema] = Field(default_factory=list)
    #: Ids of challenges that must be completed first.
    requires: list[str] = Field(default_factory=list)


class ObjectiveResult(BaseModel):
    index: int
    type: ObjectiveType
    description: str
    complete: bool
    detail: str = ""


class ChallengeValidationRequest(BaseModel):
    topology: TopologySchema


class ChallengeValidationResponse(BaseModel):
    challenge_id: str
    complete: bool
    objectives: list[ObjectiveResult] = Field(default_factory=list)
    xp: int = 0
