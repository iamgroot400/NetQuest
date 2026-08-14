import { Plus } from 'lucide-react'
import type { DragEvent } from 'react'

import { SectionTitle } from '@/components/ui/Field'
import { visualForRole } from '@/lib/deviceVisuals'
import { DEVICE_PRESETS, type DevicePreset } from '@/lib/devices'
import { useTopologyStore } from '@/stores/topologyStore'

export const PALETTE_MIME = 'application/netquest-device'

const GROUPS: Array<{ role: DevicePreset['role']; label: string }> = [
  { role: 'endpoint', label: 'Endpoints' },
  { role: 'infrastructure', label: 'Infrastructure' },
  { role: 'service', label: 'Servers' },
]

/** Where a click-to-add device lands, spread out so they do not stack. */
function nextPlacement(count: number) {
  const column = count % 3
  const row = Math.floor(count / 3)
  return { x: column * 200 - 200, y: row * 110 - 60 }
}

export function DevicePalette() {
  const addDevice = useTopologyStore((state) => state.addDevice)
  const deviceCount = useTopologyStore((state) => state.devices.length)

  const onDragStart = (event: DragEvent, presetId: string) => {
    event.dataTransfer.setData(PALETTE_MIME, presetId)
    event.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div className="p-3">
      <SectionTitle>Devices</SectionTitle>
      <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
        Drag onto the canvas, or click to add.
      </p>

      <div className="space-y-3">
        {GROUPS.map((group) => (
          <div key={group.role}>
            <h4 className="mb-1 text-[10px] font-medium tracking-wide text-ink-faint">
              {group.label}
            </h4>
            <div className="flex flex-col gap-1.5">
              {DEVICE_PRESETS.filter((preset) => preset.role === group.role).map(
                (preset) => {
                  const visual = visualForRole(preset.id)
                  const Icon = visual.icon
                  const ports = preset.services?.length ?? 0
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      draggable
                      onDragStart={(event) => onDragStart(event, preset.id)}
                      onClick={() => addDevice(preset.id, nextPlacement(deviceCount))}
                      title={preset.blurb}
                      className="group flex cursor-grab items-center gap-2.5 rounded-md border border-line bg-panel px-2.5 py-2 text-left transition-colors hover:border-ink-faint hover:bg-raised active:cursor-grabbing"
                    >
                      <span
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${visual.chip} ${visual.text}`}
                      >
                        <Icon size={15} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] font-medium text-ink">
                          {preset.label}
                        </span>
                        <span className="block truncate text-[11px] text-ink-faint">
                          {ports > 0
                            ? preset.services!.map((s) => s.port).join(', ')
                            : `${preset.ports} port${preset.ports > 1 ? 's' : ''}`}
                        </span>
                      </span>
                      <Plus
                        size={14}
                        className="shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100"
                      />
                    </button>
                  )
                },
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
