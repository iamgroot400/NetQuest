# NetQuest

**An open-source, game-like network simulator you learn networking by breaking.**

Build a network on a canvas, give the machines real addresses, run `ping`, and
watch every frame cross every cable. Then pull a cable out, get the subnet mask
wrong, point a host at a gateway that does not exist — and watch it genuinely
stop working.

```text
PC-01 ─────┐
           │
PC-02 ─────┼──── Switch ───── Router ───── Server
           │
PC-03 ─────┘
```

Nothing here is a mock-up. There is no code path that can print `Reply from …`
without a frame having actually arrived.

```bash
git clone <repository>
cd network-simulator
docker compose up --build
```

Then open **http://localhost:3000**.

---

## What it does

- **Topology editor** — drag PCs, switches, routers, firewalls, DNS servers,
  DHCP servers and web servers onto a canvas, cable them together, move,
  rename and delete them, zoom and pan.
- **Real device configuration** — IPv4 addresses, subnet masks, default
  gateways, per-interface shutdown, static routes, listening services, DNS
  zones, DHCP pools, firewall rules, NAT and VPN tunnels. Every field feeds
  the simulation.
- **A real protocol engine** — Ethernet framing, MAC learning and flooding, ARP
  request/reply with a cache, IPv4 forwarding with longest-prefix matching and
  TTL decrement, ICMP echo plus destination-unreachable/time-exceeded, TCP/UDP
  with a real SYN → SYN-ACK/RST handshake, DNS (A/CNAME/MX, CNAME chains,
  NXDOMAIN), DHCP (DISCOVER/OFFER/REQUEST/ACK, pools, leases), a stateful
  inline firewall, source NAT, and UDP-tunnelled VPN.
- **Per-device terminals** — `ipconfig`, `ping`, `traceroute`, `nslookup`,
  `dig`, `connect`, `curl`, `arp`, `ip addr`/`ip route`, `netstat`, `services`,
  `dhcp renew`/`release`, `show mac-address-table`, `show ip route`,
  `show access-list`, `show ip nat translations`, and more — all reading live
  state.
- **Connection Tester** — pick a source, a destination (address or name), a
  port and a protocol, and get back exactly what happened: open, refused
  (host said no), filtered (something in between dropped it silently),
  unreachable, or a DNS failure — with the full path and where it stopped.
- **Packet visualisation** — a hop-by-hop animation you can play, pause, step
  and replay, with an event log and a packet inspector showing the real
  headers at every layer, including what rides inside a VPN tunnel.
- **Missions** — 21 data-driven challenges across building, switching,
  routing, DNS/DHCP, firewalls/NAT/VPN and troubleshooting, validated by
  running the actual engine, each with a post-solve explanation of what
  happened and why.
- **XP and levels** — progress through Ethernet → IPv4 → ARP → Switching →
  Routing → DNS → DHCP → Ports & Services → Firewalls → NAT & Tunnels,
  unlocking missions as you go.
- **Save / load / export** — a topology is a plain JSON file.

## How the simulator works

The frontend owns one **topology document** and posts it with every command.
The backend keeps no session state at all:

```text
POST /api/v1/simulate/command
  { topology, device_id, command: "ping 192.168.1.20" }

→ { output      : terminal lines, verbatim
    events      : ordered trace — drives the animation and the log
    packets     : one record per frame that crossed a wire
    device_state: ARP caches, MAC tables and routing tables to write back
    success     : whether the command achieved its goal }
```

Because learned tables travel back into the document, an ARP cache filled by a
`ping` is still there when you run `arp` a moment later — and saving the network
saves everything that matters and nothing that does not.

Inside the engine, a single **delivery loop** moves every frame. `ping` builds
an ICMP echo request, discovers it needs a MAC address, and the engine really
does broadcast an ARP request across the actual cables. That is why a
disconnected link, a bad netmask or a missing gateway breaks connectivity for
real:

```text
PC-01 ─ ARP who has 192.168.1.1? ──▶ Switch-01 ─ flood ──▶ Router-01
PC-01 ◀── ARP 192.168.1.1 is at 02:00:5E:00:02:00 ── Switch-01 ◀── Router-01
PC-01 ─ ICMP echo request ──▶ Switch-01 ──▶ Router-01 ─ TTL 64→63 ──▶ … ──▶ Server-01
```

A worked example of the full trace is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Running it

### With Docker (recommended)

```bash
docker compose up --build
```

| Service  | URL                          |
| -------- | ---------------------------- |
| App      | http://localhost:3000        |
| API      | http://localhost:8000        |
| API docs | http://localhost:3000/docs   |

nginx serves the built frontend and proxies `/api` to the backend, so both live
on one origin — there is no backend URL to configure and no CORS to fight.

Challenge files are mounted read-only from `./challenges`, so adding a mission
only needs a `docker compose restart backend`.

### Without Docker

```bash
# backend — http://localhost:8000
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload

# frontend — http://localhost:5173
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `localhost:8000` in development.

### Tests

```bash
cd backend && .venv/bin/pytest -v      # 283 engine, API and challenge tests
cd frontend && npm run build           # typecheck + production build
```

## Project structure

```text
network-simulator/
├── backend/
│   ├── app/
│   │   ├── api/v1/            HTTP routes
│   │   ├── challenges/        challenge loading and objective validation
│   │   ├── core/              configuration
│   │   ├── schemas/           Pydantic wire formats
│   │   ├── simulation/        ← the engine, no web framework anywhere
│   │   │   ├── core/          addressing, MACs, events, graph, delivery loop
│   │   │   ├── ethernet/  ipv4/  arp/  icmp/  routing/  transport/
│   │   │   ├── dns/  dhcp/     zone resolution, DORA exchange
│   │   │   ├── devices/       base, host, pc, server, switch, router, firewall
│   │   │   ├── commands/      per-device terminal commands
│   │   │   └── connectivity.py the shared connection-test core
│   │   └── main.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── features/          topology · devices · terminal · packets · challenges
│       ├── stores/            topology · simulation · terminal · progress · ui
│       ├── components/        app shell and UI primitives
│       ├── hooks/  lib/  types/
│       └── nginx.conf
├── challenges/                beginner · switching · routing · services · security · troubleshooting
└── docker-compose.yml
```

The engine imports nothing from FastAPI. You can drive it from a script, a test,
or a different transport entirely.

## Known limitations

This is a deliberately scoped simulator. It models the following honestly, and
nothing else:

- **Not implemented yet:** VLANs, STP, IPv6, TLS, HTTP content, wireless,
  subinterfaces, dynamic routing (OSPF/RIP/BGP), stateful TCP beyond the
  handshake (no sequence numbers, windows or retransmission).
- **No spanning tree.** A physical loop between switches really does flood
  forever; the engine caps it at 500 hops and says so in the log rather than
  hanging. That is a lesson, not a bug — but do not expect STP to save you.
- **No timing.** Frames move instantly. `ping` reports TTL and byte counts,
  which are real, but no round-trip time, because there is none to report.
- **ARP and DNS cache entries never expire.** Real caches age out after
  minutes; here an entry that vanished between two commands would look like a
  fault, not a lesson.
- **DHCP leases never expire either** — released only on request.
- **The firewall is stateful** for the return leg of a flow it already
  permitted, but has no deep packet inspection: it decides on protocol, port
  and address only.
- **Cables are always full duplex, always the right kind.** No crossover
  cables, no speed or duplex mismatch.
- **One address per interface**, and no loopback interfaces.
- **Progress is per-browser.** XP and completed missions live in localStorage;
  there are no accounts. Postgres is wired into `docker-compose.yml` behind an
  opt-in `db` profile for whoever builds that.

## Contributing

Contributions are very welcome — especially new missions, which need no
knowledge of the codebase at all.

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, style, and how to send a change
- [docs/ADDING-CHALLENGES.md](docs/ADDING-CHALLENGES.md) — write a mission in JSON
- [docs/ADDING-DEVICES.md](docs/ADDING-DEVICES.md) — add a device type
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the engine fits together

## Roadmap

| Version | Theme                                                              |
| ------- | ------------------------------------------------------------------ |
| 0.3     | VLANs and trunking; switch port configuration; STP so loops survive |
| 0.4     | DHCP relays; lease expiry and renewal timing                        |
| 0.5     | ACLs as a distinct concept from firewall rules; extended ACL syntax |
| 0.6     | Wireshark-style capture export (`.pcap`) from the packet inspector  |
| 0.7     | Accounts and shared topologies on the optional Postgres service     |
| 0.8     | Dynamic routing: RIP, then OSPF                                     |
| 0.9     | Real HTTP content and TLS on the web-server preset                  |
| 1.0     | A full guided curriculum from Ethernet to dynamic routing           |

## Licence

MIT — see [LICENSE](LICENSE).
