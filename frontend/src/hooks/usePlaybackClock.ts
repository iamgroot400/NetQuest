import { useEffect } from 'react'

import { useSimulationStore } from '@/stores/simulationStore'

/**
 * Drives event playback from a single animation frame loop.
 * The loop only runs while something is playing, so an idle app costs nothing.
 */
export function usePlaybackClock() {
  const playing = useSimulationStore((state) => state.playing)

  useEffect(() => {
    if (!playing) return

    let frame = 0
    let previous = performance.now()

    const step = (now: number) => {
      // Clamp so a backgrounded tab does not fast-forward the whole trace.
      const delta = Math.min(now - previous, 100)
      previous = now
      useSimulationStore.getState().tick(delta)
      frame = requestAnimationFrame(step)
    }

    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [playing])
}
