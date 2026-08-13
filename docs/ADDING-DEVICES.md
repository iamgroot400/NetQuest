# Adding a device type

Say you want a **hub** — a Layer 1 repeater that blindly copies every frame out
of every other port. It is a good first device: three small files and a couple
of registrations.

## 1. The behaviour

`backend/app/simulation/devices/hub.py`:

```python
from ..core.events import EventType
from ..core.models import Emission, Interface
from .base import Device


class Hub(Device):
    kind = "hub"

    def receive_frame(self, frame, in_interface, engine) -> list[Emission]:
        """A hub has no memory: everything goes everywhere else."""
        targets = [i for i in self.enabled_interfaces if i.id != in_interface.id]
        engine.log(
            EventType.FRAME_FLOODED,
            f"{self.name}: repeating the frame out of {len(targets)} other ports",
            device=self,
            interface=in_interface,
            frame=frame,
        )
        return [Emission(interface_id=i.id, frame=frame) for i in targets]
```

`Device` gives you `interfaces`, `config`, `arp_table`, `interface()`,
`enabled_interfaces`, `ip_interfaces` and `owns_ip()`. The only required method
is `receive_frame`, which returns the frames this device wants to send.

If your device has learned state to keep between commands, override `state()`
and `load_state()` — see `switch.py`.

For a Layer 3 device, subclass `Host` (end station: same-subnet-or-gateway) or
`Router` (routing table, TTL, ICMP errors) instead of `Device`.

## 2. Register it

`backend/app/schemas/topology.py`:

```python
class DeviceType(str, Enum):
    ...
    HUB = "hub"
```

`backend/app/simulation/loader.py`:

```python
DEVICE_CLASSES = {
    ...
    DeviceType.HUB: Hub,
}
```

## 3. Give it commands

`backend/app/simulation/commands/hub.py`:

```python
from .common import show_interfaces
from .registry import Command, CommandResult, CommandSet

HUB_COMMANDS = CommandSet([
    Command(
        name="show interfaces",
        summary="Show port status and what is plugged into each one",
        handler=lambda ctx: CommandResult(output=show_interfaces(ctx.network, ctx.device)),
    ),
    Command(name="help", summary="List available commands", handler=cmd_help),
])
```

`backend/app/simulation/commands/__init__.py`:

```python
COMMAND_SETS = {
    ...
    "hub": HUB_COMMANDS,
}
```

The key is `Device.kind`. Commands may be several words long; resolution matches
the longest registered name against the leading tokens.

## 4. Frontend

`frontend/src/types/index.ts`:

```ts
export type DeviceType = 'pc' | 'switch' | 'router' | 'server' | 'hub'
```

`frontend/src/lib/devices.ts` — the profile drives the palette, the default
name, the port count, and whether the config panel offers address fields:

```ts
hub: {
  label: 'Hub',
  prefix: 'Hub',
  ports: 4,
  addressable: false,
  blurb: 'Layer 1. Repeats every frame out of every other port.',
},
```

Then add an icon and colour in three small maps — `DeviceNode.tsx`,
`DevicePalette.tsx` and `Canvas.tsx` (minimap) — and add a `--color-hub` token
in `index.css`. If the device needs its own configuration UI, add a component in
`features/devices/` and branch to it in `ConfigPanel.tsx`; otherwise an existing
one usually fits.

## 5. Test it

Add a builder method in `backend/tests/builders.py`, then test the behaviour
that makes the device different. For the hub, that a frame reaches ports the
destination is not on:

```python
def test_a_hub_repeats_to_every_port(self):
    net = TopologyBuilder()
    net.pc("PC-01", "192.168.1.10")
    net.pc("PC-02", "192.168.1.20")
    net.pc("PC-03", "192.168.1.30")
    net.hub("Hub-01", ports=4)
    net.link("PC-01", 0, "Hub-01", 0)
    net.link("PC-02", 0, "Hub-01", 1)
    net.link("PC-03", 0, "Hub-01", 2)

    result = run_command(net.build(), net.device_id("PC-01"), "ping 192.168.1.20 -n 1")
    assert result.success
    # Unlike a switch, the hub never stops bothering PC-03.
    assert any(e.device_name == "PC-03" for e in result.events)
```

## Checklist

- [ ] `Device` subclass with `receive_frame`
- [ ] `state()` / `load_state()` if it learns anything
- [ ] `DeviceType` enum member
- [ ] `DEVICE_CLASSES` entry
- [ ] `CommandSet` and a `COMMAND_SETS` entry
- [ ] Frontend `DeviceType`, profile, icon, colour
- [ ] Tests for the behaviour that makes it distinct
- [ ] A mission that teaches it, if it earns one
