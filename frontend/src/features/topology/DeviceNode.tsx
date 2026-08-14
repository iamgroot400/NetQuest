import { Handle, Position, type NodeProps } from '@xyflow/react'
import { TriangleAlert } from 'lucide-react'
import { memo } from 'react'

import { deviceSubtitle, visualFor } from '@/lib/deviceVisuals'
import { activeDeviceIds, useSimulationStore } from '@/stores/simulationStore'
import { useTopologyStore } from '@/stores/topologyStore'
import { useValidationStore } from '@/stores/validationStore'

export interface DeviceNodeData extends Record<string, unknown> {
  deviceId: string
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
  const issues = useValidationStore((state) => state.issues)

  if (!device) return null

  const errorCount = issues.filter(
    (i) => i.device_id === deviceId && i.severity === 'error',
  ).length
  const visual = visualFor(device)
  const Icon = visual.icon
  const openPorts = device.config.services.filter((s) => s.enabled).length
  const isDown = device.interfaces.length > 0 && device.interfaces.every((i) => !i.enabled)

  return (
    <div
      className={`group relative w-[158px] rounded-lg border bg-panel px-2.5 py-2 shadow-lg transition-colors ${
        selected ? 'border-accent' : 'border-line hover:border-ink-faint'
      } ${isDown ? 'opacity-55' : ''}`}
    >
      {isActive ? (
        <span
          aria-hidden
          className={`nq-active-ring pointer-events-none absolute -inset-1 rounded-xl ring-2 ${visual.ring}`}
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
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${visual.chip} ${visual.text}`}
        >
          <Icon size={15} strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] leading-tight font-semibold text-ink">
            {device.name}
          </span>
          <span className="block truncate font-mono text-[11px] leading-tight text-ink-faint">
            {deviceSubtitle(device)}
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

      {openPorts > 0 ? (
        <div className="mt-1.5 flex flex-wrap gap-1 border-t border-line-soft pt-1.5">
          {device.config.services
            .filter((s) => s.enabled)
            .slice(0, 4)
            .map((service) => (
              <span
                key={`${service.protocol}-${service.port}`}
                title={`${service.name} on ${service.port}/${service.protocol.toLowerCase()}`}
                className="rounded bg-raised px-1 font-mono text-[9px] text-ink-faint"
              >
                {service.port}
              </span>
            ))}
        </div>
      ) : null}
    </div>
  )
}

export const DeviceNode = memo(DeviceNodeComponent)
