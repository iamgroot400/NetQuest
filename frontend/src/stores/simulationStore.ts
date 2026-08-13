/**
 * Playback of a command's event trace.
 *
 * The backend returns the whole trace at once. Replaying it on a clock gives
 * play, pause, step and speed control for free, and keeps the animation exactly
 * in step with the log and the inspector.
 */

import { create } from 'zustand'

import type { PacketSnapshot, SimEvent } from '@/types'

/** How long a frame takes to cross one cable, at 1x. */
export const TRANSMIT_MS = 620
/** Everything else — a table lookup, a decision — is a quick beat. */
export const STEP_MS = 90

export const SPEEDS = [0.5, 1, 2, 4] as const

export interface Transit {
  linkId: string
  fromDeviceId: string
  toDeviceId: string
  frameUid: string | null
  progress: number
}

interface SimulationState {
  events: SimEvent[]
  packets: PacketSnapshot[]
  packetsByUid: Record<string, PacketSnapshot>

  /** Number of events revealed so far; the last one may still be animating. */
  cursor: number
  elapsed: number
  playing: boolean
  speed: number
  transit: Transit | null
  selectedFrameUid: string | null
  running: boolean
  error: string | null

  load: (events: SimEvent[], packets: PacketSnapshot[]) => void
  clear: () => void
  setRunning: (running: boolean) => void
  setError: (error: string | null) => void

  play: () => void
  pause: () => void
  toggle: () => void
  restart: () => void
  stepForward: () => void
  jumpToEnd: () => void
  setSpeed: (speed: number) => void
  tick: (deltaMs: number) => void

  selectFrame: (frameUid: string | null) => void
}

function durationFor(event: SimEvent | undefined): number {
  if (!event) return STEP_MS
  return event.type === 'frame_transmitted' ? TRANSMIT_MS : STEP_MS
}

function transitFor(event: SimEvent | undefined): Transit | null {
  if (!event || event.type !== 'frame_transmitted') return null
  if (!event.link_id || !event.from_device_id || !event.to_device_id) return null
  return {
    linkId: event.link_id,
    fromDeviceId: event.from_device_id,
    toDeviceId: event.to_device_id,
    frameUid: event.frame_uid,
    progress: 0,
  }
}

export const useSimulationStore = create<SimulationState>()((set, get) => {
  /** Reveal event `index` and start its animation. */
  function begin(index: number) {
    const { events } = get()
    const event = events[index]
    set({
      cursor: index + 1,
      elapsed: 0,
      transit: transitFor(event),
      selectedFrameUid: event?.frame_uid ?? get().selectedFrameUid,
    })
  }

  return {
    events: [],
    packets: [],
    packetsByUid: {},
    cursor: 0,
    elapsed: 0,
    playing: false,
    speed: 1,
    transit: null,
    selectedFrameUid: null,
    running: false,
    error: null,

    load: (events, packets) =>
      set({
        events,
        packets,
        packetsByUid: Object.fromEntries(packets.map((p) => [p.frame_uid, p])),
        cursor: 0,
        elapsed: 0,
        transit: null,
        selectedFrameUid: null,
        // A trace with nothing on the wire has nothing to animate.
        playing: events.length > 0,
        error: null,
      }),

    clear: () =>
      set({
        events: [],
        packets: [],
        packetsByUid: {},
        cursor: 0,
        elapsed: 0,
        playing: false,
        transit: null,
        selectedFrameUid: null,
      }),

    setRunning: (running) => set({ running }),
    setError: (error) => set({ error }),

    play: () => {
      const { events, cursor } = get()
      if (!events.length) return
      if (cursor >= events.length) {
        set({ cursor: 0, elapsed: 0, transit: null })
      }
      set({ playing: true })
    },

    pause: () => set({ playing: false }),

    toggle: () => (get().playing ? get().pause() : get().play()),

    restart: () => {
      if (!get().events.length) return
      set({ cursor: 0, elapsed: 0, transit: null, playing: true })
    },

    stepForward: () => {
      const { cursor, events } = get()
      set({ playing: false })
      if (cursor >= events.length) return
      begin(cursor)
      // A step is instantaneous: show the frame mid-flight rather than animating.
      set((state) => ({
        transit: state.transit ? { ...state.transit, progress: 1 } : null,
        elapsed: durationFor(events[cursor]),
      }))
    },

    jumpToEnd: () =>
      set((state) => ({
        cursor: state.events.length,
        elapsed: 0,
        playing: false,
        transit: null,
      })),

    setSpeed: (speed) => set({ speed }),

    tick: (deltaMs) => {
      const state = get()
      if (!state.playing || !state.events.length) return

      if (state.cursor === 0) {
        begin(0)
        return
      }

      const index = state.cursor - 1
      const current = state.events[index]
      const duration = durationFor(current)
      const elapsed = state.elapsed + deltaMs * state.speed

      if (elapsed >= duration) {
        if (state.cursor < state.events.length) {
          begin(state.cursor)
        } else {
          set({ playing: false, transit: null, elapsed: duration })
        }
        return
      }

      set({
        elapsed,
        transit: state.transit
          ? { ...state.transit, progress: Math.min(elapsed / duration, 1) }
          : null,
      })
    },

    selectFrame: (frameUid) => set({ selectedFrameUid: frameUid }),
  }
})

/**
 * Events revealed so far — what the log and inspector are allowed to show.
 *
 * Call this during render, never inside a store selector: it builds a new
 * array every time, and a selector that never returns the same reference
 * re-renders forever.
 */
export function revealedEvents(events: SimEvent[], cursor: number): SimEvent[] {
  return events.slice(0, cursor)
}

/** The device the simulation is currently "inside", for canvas highlighting. */
export function activeDeviceIds(state: SimulationState): string[] {
  const current = state.events[state.cursor - 1]
  if (!current) return []
  if (state.transit) return [state.transit.fromDeviceId, state.transit.toDeviceId]
  return current.device_id ? [current.device_id] : []
}
