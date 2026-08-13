/** Per-device terminal scrollback and command history. */

import { create } from 'zustand'

export type LineKind = 'prompt' | 'output' | 'error' | 'system'

export interface TerminalLine {
  id: number
  text: string
  kind: LineKind
}

interface TerminalState {
  buffers: Record<string, TerminalLine[]>
  history: Record<string, string[]>
  append: (deviceId: string, lines: Array<{ text: string; kind?: LineKind }>) => void
  remember: (deviceId: string, command: string) => void
  clear: (deviceId: string) => void
  reset: () => void
}

let lineId = 0

/** Keeps long sessions from growing without bound. */
const MAX_LINES = 500

export const useTerminalStore = create<TerminalState>()((set) => ({
  buffers: {},
  history: {},

  append: (deviceId, lines) =>
    set((state) => {
      const existing = state.buffers[deviceId] ?? []
      const added = lines.map(({ text, kind = 'output' }) => {
        lineId += 1
        return { id: lineId, text, kind }
      })
      const combined = [...existing, ...added]
      return {
        buffers: {
          ...state.buffers,
          [deviceId]: combined.slice(-MAX_LINES),
        },
      }
    }),

  remember: (deviceId, command) =>
    set((state) => {
      const existing = state.history[deviceId] ?? []
      if (existing[existing.length - 1] === command) return state
      return {
        history: { ...state.history, [deviceId]: [...existing, command].slice(-50) },
      }
    }),

  clear: (deviceId) =>
    set((state) => ({ buffers: { ...state.buffers, [deviceId]: [] } })),

  reset: () => set({ buffers: {}, history: {} }),
}))
