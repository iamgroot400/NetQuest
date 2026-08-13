import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Monitor, Network, Router, Server, TriangleAlert } from 'lucide-react'
import { memo } from 'react'

import { useTopologyStore } from '@/stores/topologyStore'
import { activeDeviceIds, useSimulationStore } from '@/stores/simulationStore'
import { useValidationStore } from '@/stores/validationStore'
import type { DeviceType } from '@/types'

export interface DeviceNodeData extends Record<string, unknown> {
  deviceId: string
}

const ICONS: Record<DeviceType, typeof Monitor> = {
  pc: Monitor,
  switch: Network,
  router: Router,
  server: Server,
}

/** Matches the CSS custom properties so every surface agrees on device colour. */
const ACCENTS: Record<DeviceType, { text: string; ring: string; chip: string }> = {
  pc: { text: 'text-pc', ring: 'ring-pc/60', chip: 'bg-pc/10' },
  switch: { text: 'text-switch', ring: 'ring-switch/60', chip: 'bg-switch/10' },
  router: { text: 'text-router', ring: 'ring-router/60', chip: 'bg-router/10' },
  server: { text: 'text-server', ring: 'ring-server/60', chip: 'bg-server/10' },
}

const HANDLES = [
  { id: 't', position: Position.Top, style: { left: '50%', top: -5 } },
  { id: 'r', position: Position.Right, style: { top: '50%', right: -5 } },
  { id: 'b', position: Position.Bottom, style: { left: '50%', bottom: -5 } },
  { id: 'l', position: Position.Left, style: { top: '50%', left: -5 } },
] as const

function DeviceNodeComponent({ data, selected }: NodeProps) {
  const { deviceId } = data as DeviceNodeData

  const device = useTopologyStore((state) =>
    state.devices.find((d) => d.id === deviceId),
  )
  const isActive = useSimulationStore((state) =>
    activeDeviceIds(state).includes(deviceId),
  )
  const errorCount = useValidationStore(
    (state) =>
      state.issues.filter((i) => i.device_id === deviceId && i.severity === 'error')
        .length,
  )

  if (!device) return null

  const Icon = ICONS[device.type]
  const accent = ACCENTS[device.type]
  const addressed = device.interfaces.find((i) => i.ipv4)
  const subtitle =
    device.type === 'switch'
      ? `${device.interfaces.length} ports`
      : (addressed?.ipv4 ?? 'no address')

  return (
    <div
      className={`group relative w-[152px] rounded-lg border bg-panel px-2.5 py-2 shadow-lg transition-colors ${
        selected ? 'border-accent' : 'border-line hover:border-ink-faint'
      }`}
    >
      {isActive ? (
        <span
          aria-hidden
          className={`nq-active-ring pointer-events-none absolute -inset-1 rounded-xl ring-2 ${accent.ring}`}
        />
      ) : null}

      {HANDLES.map((handle) => (
        <Handle
          key={handle.id}
          id={handle.id}
          type="source"
          position={handle.position}
          className="!h-2.5 !w-2.5 !border !border-line !bg-raised opacity-0 transition-opacity group-hover:opacity-100"
          style={handle.style}
        />
      ))}

      <div className="flex items-center gap-2">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${accent.chip} ${accent.text}`}
        >
          <Icon size={15} strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] leading-tight font-semibold text-ink">
            {device.name}
          </span>
          <span className="block truncate font-mono text-[11px] leading-tight text-ink-faint">
            {subtitle}
          </span>
        </span>
        {errorCount > 0 ? (
          <span
            className="shrink-0 text-bad"
            title={`${errorCount} configuration problem${errorCount > 1 ? 's' : ''}`}
          >
            <TriangleAlert size={14} />
          </span>
        ) : null}
      </div>
    </div>
  )
}

export const DeviceNode = memo(DeviceNodeComponent)
