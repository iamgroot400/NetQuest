# Adding a challenge

A challenge is one JSON file. You do not need to touch any code, and you do not
need to understand the simulator internals.

1. Drop a file into `challenges/<category>/<your-id>.json`.
2. `docker compose restart backend` (files are mounted, not baked).
3. It appears in the mission list.

Categories are `beginner`, `switching`, `routing` and `troubleshooting`.

## The smallest possible mission

```json
{
  "id": "first-contact",
  "name": "First Contact",
  "category": "beginner",
  "difficulty": 1,
  "xp": 100,
  "level": 1,
  "description": "Two computers, one cable. Make them talk.",
  "brief": "Drag two PCs onto the canvas, cable them together, and give each an address in the same network.",
  "hints": ["Drag a PC from the palette twice.", "Use 192.168.1.10 and .20."],
  "topology": null,
  "objectives": [
    { "type": "device_exists", "device_type": "pc", "count": 2 },
    { "type": "link_exists", "a": "PC-01", "b": "PC-02" },
    { "type": "ping_succeeds", "source": "PC-01", "destination": "PC-02" }
  ]
}
```

## Fields

| Field         | Meaning                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `id`          | Unique, kebab-case. Used in URLs and in other missions' `requires`.      |
| `name`        | Shown in the list and the completion modal.                             |
| `category`    | Which group it appears under.                                           |
| `difficulty`  | 1–5, rendered as stars.                                                 |
| `xp`          | Awarded once, on first completion.                                      |
| `level`       | Which progression level it belongs to; also sorts the list.             |
| `description` | One line.                                                               |
| `brief`       | The scenario. Newlines are preserved — use them.                        |
| `hints`       | Revealed one at a time, on request. Order them from nudge to answer.    |
| `topology`    | A starting network, or `null` for an empty canvas.                      |
| `requires`    | Mission ids that must be completed first. Locks this one until then.    |
| `objectives`  | What must be true to finish. All must pass.                             |

## Objective types

| Type                   | Fields                                            | Passes when                                            |
| ---------------------- | ------------------------------------------------- | ------------------------------------------------------ |
| `device_exists`        | `device_type` or `device`, `count`                | At least `count` matching devices are on the canvas.    |
| `link_exists`          | `a`, `b` (device names)                           | A cable joins them **and** it is connected.             |
| `interface_configured` | `device`, optional `interface`, `ipv4`, `netmask`, `gateway` | The named values match. Omit a value to accept anything valid. |
| `in_subnet`            | `device`, `subnet`, optional `netmask`            | Some interface on the device falls inside that network. |
| `ping_succeeds`        | `source`, `destination`                           | A real ping gets a reply.                               |
| `ping_fails`           | `source`, `destination`                           | A real ping does **not** get a reply.                   |

`destination` may be a literal address or a device name — a name resolves to
that device's first enabled address.

Devices are matched **by name**, so rely on the default names the app assigns:
`PC-01`, `PC-02`, `Switch-01`, `Router-01`, `Server-01`, and so on.

Connectivity objectives run the actual simulation engine. There is no way to
make one pass without the packet arriving.

### Descriptions come free

Omit `description` on an objective and a readable one is generated
("Connect PC-01 to Switch-01", "PC-01 can ping Server-01"). Set it when you want
to phrase things in the mission's own voice.

## Shipping a starting network

The easiest way to author a `topology` is to build it in the app and use
**Save** — the exported JSON is exactly the shape the field expects. Paste it in
whole.

For a troubleshooting mission, build the network **working**, save it, then
break one thing by hand in the JSON:

```jsonc
// The classic: a gateway nobody answers for.
"config": { "gateway": "192.168.10.254", "static_routes": [] }

// Or a cable that is still drawn but carries nothing.
{ "id": "lnk-3", "a": {...}, "b": {...}, "status": "down" }
```

## Writing a good mission

- **Break exactly one thing.** Two faults at once teaches guessing, not method.
- **Make the symptom visible before the cause.** The best missions have the
  learner run `ping`, read the event log, and find the fault themselves.
- **Let something still work.** "PC-01 can reach PC-02 but not the server"
  narrows the search and models real triage.
- **Write hints as a ladder.** Hint 1 says where to look, the last one says what
  to change.
- **Prove it is solvable.** Add a test in `backend/tests/test_challenges.py`:
  assert the shipped topology fails, apply the fix, assert it passes. Every
  bundled mission has one.

```python
def test_my_mission(self):
    topology = starting_topology("my-mission")
    assert not check("my-mission", topology).complete

    device(topology, "PC-01").config.gateway = "192.168.10.1"
    result = check("my-mission", topology)
    assert result.complete, unmet(result)
```

## Checks the loader performs

A malformed file is skipped with an error in the backend log rather than taking
the app down. Duplicate ids are rejected. Run the test suite to catch problems
before you open a pull request:

```bash
cd backend && pytest tests/test_challenges.py -v
```
