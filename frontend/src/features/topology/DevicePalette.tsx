import { Monitor, Network, Plus, Router, Server } from 'lucide-react'
import type { DragEvent } from 'react'

import { SectionTitle } from '@/components/ui/Field'
import { DEVICE_ORDER, DEVICE_PROFILES } from '@/lib/devices'
import { useTopologyStore } from '@/stores/topologyStore'
import type { DeviceType } from '@/types'

export const PALETTE_MIME = 'application/netquest-device'

const ICONS: Record<DeviceType, typeof Monitor> = {
  pc: Monitor,
  switch: Network,
  router: Router,
  server: Server,
}

const ACCENTS: Record<DeviceType, string> = {
  pc: 'text-pc bg-pc/10',
  switch: 'text-switch bg-switch/10',
  router: 'text-router bg-router/10',
  server: 'text-server bg-server/10',
}

/** Where a click-to-add device lands, spread out so they do not stack. */
function nextPlacement(count: number) {
  const column = count % 3
  const row = Math.floor(count / 3)
  return { x: column * 200 - 200, y: row * 110 - 60 }
}

export function DevicePalette() {
  const addDevice = useTopologyStore((state) => state.addDevice)
  const deviceCount = useTopologyStore((state) => state.devices.length)

  const onDragStart = (event: DragEvent, type: DeviceType) => {
    event.dataTransfer.setData(PALETTE_MIME, type)
    event.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div className="p-3">
      <SectionTitle>Devices</SectionTitle>
      <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
        Drag onto the canvas, or click to add.
      </p>
      <div className="flex flex-col gap-1.5">
        {DEVICE_ORDER.map((type) => {
          const profile = DEVICE_PROFILES[type]
          const Icon = ICONS[type]
          return (
            <button
              key={type}
              type="button"
              draggable
              onDragStart={(event) => onDragStart(event, type)}
              onClick={() => addDevice(type, nextPlacement(deviceCount))}
              title={profile.blurb}
              className="group flex cursor-grab items-center gap-2.5 rounded-md border border-line bg-panel px-2.5 py-2 text-left transition-colors hover:border-ink-faint hover:bg-raised active:cursor-grabbing"
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${ACCENTS[type]}`}
              >
                <Icon size={15} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-ink">
                  {profile.label}
                </span>
                <span className="block truncate text-[11px] text-ink-faint">
                  {profile.ports} port{profile.ports > 1 ? 's' : ''}
                </span>
              </span>
              <Plus
                size={14}
                className="shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100"
              />
            </button>
          )
        })}
      </div>
    </div>
  )
}
