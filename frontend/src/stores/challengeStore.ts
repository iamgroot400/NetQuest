/** Challenge definitions fetched from the backend. */

import { create } from 'zustand'

import { ApiError, api } from '@/lib/api'
import type { Challenge } from '@/types'

interface ChallengeState {
  challenges: Challenge[]
  loading: boolean
  error: string | null
  load: () => Promise<void>
}

export const useChallengeStore = create<ChallengeState>()((set, get) => ({
  challenges: [],
  loading: false,
  error: null,

  load: async () => {
    if (get().loading) return
    set({ loading: true, error: null })
    try {
      set({ challenges: await api.challenges(), loading: false })
    } catch (error) {
      set({
        loading: false,
        error:
          error instanceof ApiError
            ? error.message
            : 'Could not load the challenge list.',
      })
    }
  },
}))

/** A challenge unlocks once every prerequisite has been completed. */
export function isLocked(challenge: Challenge, completed: string[]): boolean {
  return challenge.requires.some((required) => !completed.includes(required))
}
