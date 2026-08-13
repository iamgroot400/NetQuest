# Architecture

## The one idea that shapes everything

**The frontend owns the network; the backend is a pure function over it.**

There are no sessions, no server-side topology, no synchronisation. Every request
carries the whole topology document and gets back a complete answer:

```text
POST /api/v1/simulate/command
  { topology, device_id, command }

→ { output, events, packets, device_state, success }
```

This buys a lot:

- **Save/load is free.** The document _is_ the save file.
- **The engine is trivially testable.** No fixtures, no server, no mocking.
- **The animation is deterministic.** The whole trace arrives at once, so play,
  pause, step, speed and replay all work on the same data.
- **Learned state still persists.** ARP caches and MAC tables come back in
  `device_state` and the frontend writes them into the document, so the next
  command sees them.

## Layers

```text
┌──────────────────────────────────────────────────────────┐
│ frontend/src                                             │
│   features/  topology · devices · terminal · packets ·   │
│              challenges                                  │
│   stores/    topology · simulation · terminal ·          │
│              progress · ui · validation                  │
└───────────────────────┬──────────────────────────────────┘
                        │  HTTP, same origin, /api/v1
┌───────────────────────▼──────────────────────────────────┐
│ backend/app/api/v1        thin routes, no logic          │
│ backend/app/schemas       Pydantic wire formats          │
│ backend/app/simulation/   ← the engine                   │
│      loader.py            schema → engine objects        │
│      core/engine.py       the delivery loop              │
│      devices/             what each box does with a frame│
│      commands/            what each box says             │
└──────────────────────────────────────────────────────────┘
```

`app/simulation/` imports nothing from FastAPI or Pydantic except through
`loader.py`, which is the single bridge. You can drive the engine from a plain
script.

## The delivery loop

`SimulationEngine.run()` in `core/engine.py` is the only code that moves a frame
between devices. Everything else — ping, ARP, an ICMP error — goes through it.

```python
queue = deque(emissions)
while queue:
    device, emission = queue.popleft()
    iface = device.interface(emission.interface_id)

    # Each of these is a real reason a network fails, and each logs an event.
    if not iface.enabled:        drop("interface is down");    continue
    link = network.link_for(iface.id)
    if link is None:             drop("no cable");             continue
    if not link.is_up:           drop("cable disconnected");   continue
    peer_device, peer_iface = network.peer_of(iface.id)
    if not peer_iface.enabled:   drop("far end is down");      continue

    log(FRAME_TRANSMITTED, link=link, from=device, to=peer_device)
    queue.extend(peer_device.receive_frame(frame, peer_iface, self))
```

`run()` is **re-entrant**. A router that needs to ARP for its next hop calls
`engine.resolve_arp()`, which calls `run()` again with its own queue. The hop
budget and event list are shared, so a switching loop is still bounded.

### Why nothing can fake success

`ping` does not ask "is there a path?". It builds an ICMP echo request, hands it
to the loop, and then reads the device's own inbox:

```python
device.icmp_inbox.clear()
emissions = device.send_ipv4(packet, engine)
if not emissions:
    return "Destination host unreachable."   # never even reached the wire
engine.run(device, emissions)
return reply_line_from(device.icmp_inbox)    # only what actually arrived
```

An echo reply exists only if a real device received a real frame and generated
one. That is the whole design.

## A worked example

`PC-01 (192.168.1.10, gw 192.168.1.1)` pings `Server-01 (10.0.0.50)` across
`Switch-A → Router-01 → Switch-B`:

```text
 1  PC-01     ARP Request: who has 192.168.1.1? tell 192.168.1.10
 2  PC-01     eth0 → SW-A eth0
 3  SW-A      learned 02:00:5E:00:00:00 on eth0
 4  SW-A      broadcast frame — flooding out every other port
 5  SW-A      eth1 → R1 eth0
 6  R1        ARP Reply: 192.168.1.1 is at 02:00:5E:00:02:00
 …
14  PC-01     ARP resolved 192.168.1.1 → 02:00:5E:00:02:00
15  PC-01     sending ICMP to 10.0.0.50 via 192.168.1.1
…
19  R1        TTL 64 → 63 for 10.0.0.50
20  R1        10.0.0.50 matches 10.0.0.0/24 (connected) via eth1
21  R1        ARP Request: who has 10.0.0.50? tell 10.0.0.1
…
38  Server-01 received echo request from 192.168.1.10 (seq=1)
39  Server-01 generating echo reply to 192.168.1.10
40  Server-01 ARP cache hit — 10.0.0.1 is at 02:00:5E:00:02:01
…
51  PC-01     received ICMP echo-reply id=1 seq=1 from 10.0.0.50
```

Note events 39–41: the reply is **routed independently**, using the server's own
default gateway. That is why the "Silent Server" mission works — a server with
no gateway receives every request and can answer none of them.

## Frontend state

| Store             | Owns                                                        |
| ----------------- | ----------------------------------------------------------- |
| `topologyStore`   | devices, links, selection. Persisted to localStorage.        |
| `simulationStore` | the event trace and its playback cursor                      |
| `terminalStore`   | per-device scrollback and command history                    |
| `progressStore`   | XP, completed missions. Persisted.                           |
| `validationStore` | configuration problems from the backend                      |
| `uiStore`         | panel layout and toasts                                      |

### A rule worth knowing

**A zustand selector must return a stable reference.** A selector like
`(state) => state.issues.filter(...)` builds a new array every call, never
compares equal, and re-renders forever. Select the stable slice and derive in
render instead:

```ts
const issues = useValidationStore((s) => s.issues)          // stable
const mine = issues.filter((i) => i.device_id === deviceId) // derive here
```

### Animation

The trace carries `link_id`, `from_device_id` and `to_device_id` on every
`frame_transmitted` event. `usePlaybackClock` advances a cursor on a single
`requestAnimationFrame` loop; `CableEdge` interpolates a dot between its two
endpoints. Because cable paths are straight lines, the position is plain linear
interpolation — no path measurement, exact at any zoom.

## Adding to the simulator

- A new device type → [ADDING-DEVICES.md](ADDING-DEVICES.md)
- A new mission → [ADDING-CHALLENGES.md](ADDING-CHALLENGES.md)
- A new protocol → add a package under `app/simulation/`, an `EtherType` or
  `IPProtocol` member, and handling in the devices that should understand it.
  Add `EventType` members so the learner can watch it happen.
