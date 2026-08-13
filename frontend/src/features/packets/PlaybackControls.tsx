import { Pause, Play, RotateCcw, SkipForward } from 'lucide-react'

import { IconButton } from '@/components/ui/Button'
import { SPEEDS, useSimulationStore } from '@/stores/simulationStore'

/** Floating transport controls for the event trace, shown once there is one. */
export function PlaybackControls() {
  const total = useSimulationStore((state) => state.events.length)
  const cursor = useSimulationStore((state) => state.cursor)
  const playing = useSimulationStore((state) => state.playing)
  const speed = useSimulationStore((state) => state.speed)

  const toggle = useSimulationStore((state) => state.toggle)
  const restart = useSimulationStore((state) => state.restart)
  const stepForward = useSimulationStore((state) => state.stepForward)
  const setSpeed = useSimulationStore((state) => state.setSpeed)

  if (total === 0) return null

  const progress = total ? (cursor / total) * 100 : 0

  return (
    <div className="pointer-events-auto absolute bottom-4 left-1/2 z-10 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-lg border border-line bg-panel/95 px-2 py-1.5 shadow-xl backdrop-blur">
        <IconButton label="Replay from the start" onClick={restart}>
          <RotateCcw size={13} />
        </IconButton>
        <IconButton
          label={playing ? 'Pause' : 'Play'}
          variant="primary"
          onClick={toggle}
        >
          {playing ? <Pause size={13} /> : <Play size={13} />}
        </IconButton>
        <IconButton
          label="Step one event"
          onClick={stepForward}
          disabled={cursor >= total}
        >
          <SkipForward size={13} />
        </IconButton>

        <div className="mx-1 h-6 w-px bg-line" />

        <div className="w-32">
          <div className="h-1 overflow-hidden rounded-full bg-raised">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-1 text-center font-mono text-[10px] text-ink-faint tabular-nums">
            {cursor} / {total} events
          </div>
        </div>

        <div className="mx-1 h-6 w-px bg-line" />

        <div className="flex items-center gap-0.5">
          {SPEEDS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setSpeed(option)}
              className={`rounded px-1.5 py-1 font-mono text-[10px] transition-colors ${
                speed === option
                  ? 'bg-accent/20 text-accent'
                  : 'text-ink-faint hover:text-ink-dim'
              }`}
            >
              {option}×
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
