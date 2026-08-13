/**
 * XP, levels and challenge completion.
 *
 * Levels are named after what you had to understand to reach them. Only the
 * first five are reachable in the MVP; the rest are shown as locked so the
 * roadmap is visible without pretending the features exist.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { ObjectiveResult } from '@/types'

export interface LevelDefinition {
  level: number
  name: string
  xp: number
  available: boolean
}

export const LEVELS: LevelDefinition[] = [
  { level: 1, name: 'Ethernet', xp: 0, available: true },
  { level: 2, name: 'IPv4', xp: 100, available: true },
  { level: 3, name: 'ARP', xp: 250, available: true },
  { level: 4, name: 'Switching', xp: 450, available: true },
  { level: 5, name: 'Routing', xp: 700, available: true },
  { level: 6, name: 'VLANs', xp: 1100, available: false },
  { level: 7, name: 'DHCP', xp: 1500, available: false },
  { level: 8, name: 'DNS', xp: 2000, available: false },
  { level: 9, name: 'NAT', xp: 2600, available: false },
  { level: 10, name: 'ACLs', xp: 3300, available: false },
]

export function levelForXp(xp: number): LevelDefinition {
  let current = LEVELS[0]!
  for (const level of LEVELS) {
    if (xp >= level.xp) current = level
  }
  return current
}

export function nextLevel(xp: number): LevelDefinition | null {
  return LEVELS.find((level) => level.xp > xp) ?? null
}

export interface Award {
  challengeId: string
  challengeName: string
  xp: number
  totalXp: number
  levelUp: LevelDefinition | null
  unlocked: string[]
}

interface ProgressState {
  xp: number
  completed: string[]
  activeChallengeId: string | null
  objectives: ObjectiveResult[]
  checking: boolean
  award: Award | null

  setActiveChallenge: (challengeId: string | null) => void
  setObjectives: (objectives: ObjectiveResult[]) => void
  setChecking: (checking: boolean) => void
  completeChallenge: (input: {
    challengeId: string
    challengeName: string
    xp: number
    unlocked: string[]
  }) => Award | null
  dismissAward: () => void
  resetProgress: () => void
}

export const useProgressStore = create<ProgressState>()(
  persist(
    (set, get) => ({
      xp: 0,
      completed: [],
      activeChallengeId: null,
      objectives: [],
      checking: false,
      award: null,

      setActiveChallenge: (challengeId) =>
        set({ activeChallengeId: challengeId, objectives: [] }),

      setObjectives: (objectives) => set({ objectives }),
      setChecking: (checking) => set({ checking }),

      completeChallenge: ({ challengeId, challengeName, xp, unlocked }) => {
        // Replaying a finished mission must not farm XP.
        if (get().completed.includes(challengeId)) return null

        const before = get().xp
        const totalXp = before + xp
        const levelUp =
          levelForXp(totalXp).level > levelForXp(before).level
            ? levelForXp(totalXp)
            : null

        const award: Award = { challengeId, challengeName, xp, totalXp, levelUp, unlocked }
        set((state) => ({
          xp: totalXp,
          completed: [...state.completed, challengeId],
          award,
        }))
        return award
      },

      dismissAward: () => set({ award: null }),

      resetProgress: () =>
        set({
          xp: 0,
          completed: [],
          activeChallengeId: null,
          objectives: [],
          award: null,
        }),
    }),
    {
      name: 'netquest.progress',
      version: 1,
      partialize: (state) => ({
        xp: state.xp,
        completed: state.completed,
        activeChallengeId: state.activeChallengeId,
      }),
    },
  ),
)
