import { useLayoutEffect, useRef } from 'react'

import { Empty } from '@/components/ui/Field'
import { SEVERITY_CLASS } from '@/lib/packets'
import { revealedEvents, useSimulationStore } from '@/stores/simulationStore'
import { useTopologyStore } from '@/stores/topologyStore'

/** Icons stay ASCII so the log reads like a console transcript. */
const MARKERS: Record<string, string> = {
  info: '·',
  success: '✓',
  warning: '!',
  error: '✕',
}

export function EventLog() {
  // Selectors must return a stable reference, so the slice happens in render
  // rather than inside the selector.
  const all = useSimulationStore((state) => state.events)
  const cursor = useSimulationStore((state) => state.cursor)
  const events = revealedEvents(all, cursor)
  const total = all.length
  const selectFrame = useSimulationStore((state) => state.selectFrame)
  const selectedFrameUid = useSimulationStore((state) => state.selectedFrameUid)
  const select = useTopologyStore((state) => state.select)

  const endRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [events.length])

  if (total === 0) {
    return (
      <Empty>
        No traffic yet. Run a command such as{' '}
        <span className="font-mono text-ink-dim">ping 192.168.1.20</span> and every
        step the network takes appears here.
      </Empty>
    )
  }

  return (
    <div className="h-full overflow-y-auto px-2 py-1.5 font-mono text-[11.5px] leading-[1.6]">
      {events.map((event) => {
        const selected = !!event.frame_uid && event.frame_uid === selectedFrameUid
        return (
          <button
            key={event.seq}
            type="button"
            onClick={() => {
              selectFrame(event.frame_uid)
              if (event.device_id) select(event.device_id)
            }}
            className={`flex w-full items-baseline gap-2 rounded px-1.5 py-[3px] text-left transition-colors hover:bg-raised ${
              selected ? 'bg-raised' : ''
            }`}
          >
            <span className="w-8 shrink-0 text-right text-ink-faint tabular-nums">
              {event.seq}
            </span>
            <span className={`w-3 shrink-0 ${SEVERITY_CLASS[event.severity]}`}>
              {MARKERS[event.severity]}
            </span>
            <span className={`min-w-0 flex-1 ${SEVERITY_CLASS[event.severity]}`}>
              {event.message}
            </span>
          </button>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}
