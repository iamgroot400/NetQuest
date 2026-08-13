import { useCallback } from 'react'

import { ApiError, api } from '@/lib/api'
import { useChallengeStore, isLocked } from '@/stores/challengeStore'
import { useProgressStore } from '@/stores/progressStore'
import { toDocument } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'

/**
 * Checks the current topology against a challenge. The backend runs the real
 * engine for connectivity objectives, so this cannot pass on appearances.
 */
export function useChallengeCheck() {
  const notify = useUiStore((state) => state.notify)

  return useCallback(
    async (challengeId: string) => {
      const progress = useProgressStore.getState()
      const challenge = useChallengeStore
        .getState()
        .challenges.find((c) => c.id === challengeId)
      if (!challenge) return

      progress.setChecking(true)
      try {
        const result = await api.validateChallenge(challengeId, toDocument())
        useProgressStore.getState().setObjectives(result.objectives)

        if (!result.complete) {
          const remaining = result.objectives.filter((o) => !o.complete).length
          notify(
            `${remaining} objective${remaining === 1 ? '' : 's'} still to go.`,
            'info',
          )
          return result
        }

        const completedBefore = useProgressStore.getState().completed
        const unlocked = useChallengeStore
          .getState()
          .challenges.filter(
            (candidate) =>
              candidate.requires.includes(challengeId) &&
              isLocked(candidate, completedBefore) &&
              !isLocked(candidate, [...completedBefore, challengeId]),
          )
          .map((candidate) => candidate.name)

        const award = useProgressStore.getState().completeChallenge({
          challengeId,
          challengeName: challenge.name,
          xp: result.xp,
          unlocked,
        })
        if (!award) notify('Mission already complete — no XP this time.', 'info')
        return result
      } catch (error) {
        notify(
          error instanceof ApiError ? error.message : 'Could not check the mission.',
          'error',
        )
        return undefined
      } finally {
        useProgressStore.getState().setChecking(false)
      }
    },
    [notify],
  )
}
