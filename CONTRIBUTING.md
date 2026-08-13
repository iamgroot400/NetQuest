# Contributing to NetQuest

Thanks for wanting to help. This project exists so people can learn networking
by doing it, so the most valuable contributions are usually the ones that make
something clearer, not the ones that add another protocol.

## Good first contributions

- **A new mission.** One JSON file, no code, no internals.
  See [docs/ADDING-CHALLENGES.md](docs/ADDING-CHALLENGES.md).
- **Better event messages.** The event log is the teaching surface. If a line
  is confusing, rewording it is a real improvement.
- **A missing failure mode.** If you can misconfigure something and the
  simulator behaves wrongly or unhelpfully, that is a bug worth filing.

## Setting up

```bash
git clone <your fork>
cd network-simulator

# Backend
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # Windows: .venv\Scripts\pip
.venv/bin/pytest                                 # 135 tests, should be green
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000

# Frontend, in another terminal
cd frontend
npm install
npm run dev                                      # http://localhost:5173
```

Or just `docker compose up --build` and edit from there.

## Before you open a pull request

```bash
cd backend  && pytest            # engine, API and challenge tests
cd frontend && npm run build     # typechecks, then bundles
```

CI runs exactly these.

## The one rule

**Nothing may fake a result.**

This is not a style preference — it is the whole point of the project. Concretely:

- No hardcoded success. `ping` reports what arrived in the device's inbox, and
  nothing else.
- No shortcut path lookups. If a frame should cross three cables, it crosses
  three cables through `SimulationEngine.run()`.
- No UI that implies a feature exists when it does not. A button either works
  or is visibly marked as coming later.
- If a limitation is real, write it down in the README rather than papering
  over it. "No spanning tree, so loops flood until the hop cap" is a better
  answer than a silent special case.

## Code style

**Python** — type hints everywhere, `from __future__ import annotations`,
dataclasses in the engine and Pydantic only at the API boundary. The engine
must not import FastAPI. Keep modules small and named after the thing they
model (`arp/table.py`, not `utils.py`).

**TypeScript** — `strict` is on and stays on. Prefer small components over
options-heavy ones. Derive state in render rather than duplicating it.

One thing worth knowing: **a zustand selector must return a stable reference.**
`(state) => state.issues.filter(...)` builds a new array every call and will
re-render forever. Select the stable slice, derive in render.

**Comments** explain *why*, not *what*. The engine has a fair number of them
because the reasons are pedagogical — a comment explaining that ARP entries
never expire on purpose is worth keeping.

## Tests

Every engine change needs a test. The bar is: **a test should describe a
mistake a learner could actually make.**

```python
def test_when_the_far_side_has_no_route_home(self):
    # The server can receive the echo request but has no gateway, so its
    # reply is dropped at its own doorstep.
    net = routed_network()
    net.devices[4].config.gateway = None
    result = ping(net, "PC-01", "10.0.0.50")
    assert not result.success
    assert "Request timed out." in joined(result)
```

`backend/tests/builders.py` has a fluent builder so tests read like diagrams.
Use `apply_state()` when a test needs a warmed-up network — the frontend writes
learned tables back between commands, and tests must too.

## Reporting a bug

Please include the topology. **Save** in the app produces a JSON file that
reproduces your network exactly — attach it. Then say what you ran, what
happened, and what you expected.

## Licence

By contributing you agree your work is released under the MIT licence.
