import { Cable, MousePointerClick, Trash2, TriangleAlert, Unplug } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Empty, Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { DEVICE_PROFILES } from '@/lib/devices'
import { useTopologyStore } from '@/stores/topologyStore'
import { useValidationStore } from '@/stores/validationStore'

import { HostConfig } from './HostConfig'
import { RouterConfig } from './RouterConfig'
import { SwitchConfig } from './SwitchConfig'

export function ConfigPanel() {
  const selectedDeviceId = useTopologyStore((state) => state.selectedDeviceId)
  const selectedLinkId = useTopologyStore((state) => state.selectedLinkId)
  const device = useTopologyStore((state) =>
    state.devices.find((d) => d.id === state.selectedDeviceId),
  )

  if (device) return <DeviceConfig deviceId={device.id} />
  if (selectedLinkId) return <LinkConfig linkId={selectedLinkId} />
  if (selectedDeviceId) return <Empty>That device no longer exists.</Empty>

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <MousePointerClick size={20} className="text-ink-faint" />
      <p className="text-xs leading-relaxed text-ink-faint">
        Select a device or a cable on the canvas to configure it.
      </p>
    </div>
  )
}

function DeviceConfig({ deviceId }: { deviceId: string }) {
  const device = useTopologyStore((state) => state.devices.find((d) => d.id === deviceId))
  const renameDevice = useTopologyStore((state) => state.renameDevice)
  const removeDevice = useTopologyStore((state) => state.removeDevice)
  // Filter in render: a selector returning a fresh array on every call would
  // never compare equal and would re-render without end.
  const allIssues = useValidationStore((state) => state.issues)
  const issues = allIssues.filter((issue) => issue.device_id === deviceId)

  const [name, setName] = useState(device?.name ?? '')
  useEffect(() => setName(device?.name ?? ''), [device?.id, device?.name])

  if (!device) return null
  const profile = DEVICE_PROFILES[device.type]

  const commitName = () => {
    const trimmed = name.trim()
    if (trimmed && trimmed !== device.name) renameDevice(device.id, trimmed)
    else setName(device.name)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-3 py-3">
        <Field
        label={profile.label}
        hint={
          <span>
            {device.interfaces.length} port{device.interfaces.length === 1 ? '' : 's'}
          </span>
        }
      >
          <TextInput
            value={name}
            onChange={(event) => setName(event.target.value)}
            onBlur={commitName}
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.currentTarget.blur()
              if (event.key === 'Escape') setName(device.name)
            }}
            className="!font-sans !text-[13px] !font-semibold"
          />
        </Field>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {issues.length > 0 ? (
          <ul className="mb-4 space-y-1.5">
            {issues.map((issue, index) => (
              <li
                key={index}
                className={`flex gap-2 rounded-md border px-2.5 py-2 text-[11px] leading-relaxed ${
                  issue.severity === 'error'
                    ? 'border-bad/30 bg-bad/5 text-bad'
                    : 'border-warn/30 bg-warn/5 text-warn'
                }`}
              >
                <TriangleAlert size={13} className="mt-px shrink-0" />
                <span>{issue.message}</span>
              </li>
            ))}
          </ul>
        ) : null}

        {device.type === 'switch' ? (
          <SwitchConfig device={device} />
        ) : device.type === 'router' ? (
          <RouterConfig device={device} />
        ) : (
          <HostConfig device={device} />
        )}
      </div>

      <div className="border-t border-line p-3">
        <Button
          variant="danger"
          size="sm"
          className="w-full"
          onClick={() => removeDevice(device.id)}
        >
          <Trash2 size={13} />
          Delete {device.name}
        </Button>
      </div>
    </div>
  )
}

function LinkConfig({ linkId }: { linkId: string }) {
  const link = useTopologyStore((state) => state.links.find((l) => l.id === linkId))
  const devices = useTopologyStore((state) => state.devices)
  const setLinkStatus = useTopologyStore((state) => state.setLinkStatus)
  const removeLink = useTopologyStore((state) => state.removeLink)

  if (!link) return <Empty>That cable no longer exists.</Empty>

  const describe = (end: { device_id: string; interface_id: string }) => {
    const device = devices.find((d) => d.id === end.device_id)
    const iface = device?.interfaces.find((i) => i.id === end.interface_id)
    return `${device?.name ?? 'unknown'} · ${iface?.name ?? '?'}`
  }

  const connected = link.status === 'up'

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-3 py-3">
        <SectionTitle>Cable</SectionTitle>
        <div className="space-y-1 font-mono text-[12px] text-ink-dim">
          <div>{describe(link.a)}</div>
          <div className="text-ink-faint">↕</div>
          <div>{describe(link.b)}</div>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        <div
          className={`flex items-center gap-2 rounded-md border px-2.5 py-2 text-[11px] ${
            connected ? 'border-ok/30 bg-ok/5 text-ok' : 'border-bad/30 bg-bad/5 text-bad'
          }`}
        >
          {connected ? <Cable size={13} /> : <Unplug size={13} />}
          {connected ? 'Connected — frames can cross.' : 'Disconnected — nothing gets through.'}
        </div>

        <Button
          size="sm"
          className="w-full"
          onClick={() => setLinkStatus(link.id, connected ? 'down' : 'up')}
        >
          {connected ? 'Disconnect cable' : 'Reconnect cable'}
        </Button>

        <p className="text-[11px] leading-relaxed text-ink-faint">
          Disconnecting leaves the cable on the canvas but stops it carrying traffic —
          handy for seeing exactly how a network fails.
        </p>
      </div>

      <div className="border-t border-line p-3">
        <Button
          variant="danger"
          size="sm"
          className="w-full"
          onClick={() => removeLink(link.id)}
        >
          <Trash2 size={13} />
          Remove cable
        </Button>
      </div>
    </div>
  )
}
