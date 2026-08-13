import { Check, Circle, Eraser, Lightbulb, Loader2, Target } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { SectionTitle } from '@/components/ui/Field'
import { useChallengeCheck } from '@/hooks/useChallengeCheck'
import { useChallengeStore } from '@/stores/challengeStore'
import { useProgressStore } from '@/stores/progressStore'
import { useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'

export function ChallengeBriefing() {
  const activeId = useProgressStore((state) => state.activeChallengeId)
  const objectives = useProgressStore((state) => state.objectives)
  const checking = useProgressStore((state) => state.checking)
  const completed = useProgressStore((state) => state.completed)
  const challenge = useChallengeStore((state) =>
    state.challenges.find((c) => c.id === activeId),
  )

  const check = useChallengeCheck()
  const reset = useTopologyStore((state) => state.reset)
  const loadDocument = useTopologyStore((state) => state.loadDocument)
  const setBottomTab = useUiStore((state) => state.setBottomTab)

  const [hintsShown, setHintsShown] = useState(0)

  if (!challenge) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <Target size={20} className="text-ink-faint" />
        <p className="text-xs leading-relaxed text-ink-faint">
          Pick a mission from the list on the left to see its briefing here.
        </p>
      </div>
    )
  }

  const isDone = completed.includes(challenge.id)

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-3 py-3">
        <div className="mb-1 flex items-center gap-2">
          <h2 className="min-w-0 flex-1 truncate text-[14px] font-semibold text-ink">
            {challenge.name}
          </h2>
          {isDone ? (
            <span className="shrink-0 rounded bg-ok/10 px-1.5 py-0.5 text-[10px] font-medium text-ok">
              COMPLETE
            </span>
          ) : null}
        </div>
        <p className="text-[11px] text-ink-faint">
          {'★'.repeat(challenge.difficulty)}
          {'☆'.repeat(Math.max(0, 5 - challenge.difficulty))} · {challenge.xp} XP ·
          Level {challenge.level}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3">
        <p className="text-[12px] leading-relaxed whitespace-pre-line text-ink-dim">
          {challenge.brief || challenge.description}
        </p>

        <section>
          <SectionTitle>Objectives</SectionTitle>
          <ul className="space-y-1">
            {challenge.objectives.map((objective, index) => {
              const result = objectives.find((o) => o.index === index)
              const done = result?.complete ?? false
              return (
                <li
                  key={index}
                  className={`flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-[11.5px] leading-relaxed ${
                    done
                      ? 'border-ok/30 bg-ok/5 text-ok'
                      : 'border-line bg-panel text-ink-dim'
                  }`}
                >
                  <span className="mt-0.5 shrink-0">
                    {done ? <Check size={12} /> : <Circle size={11} />}
                  </span>
                  <span className="min-w-0">
                    <span className="block">
                      {result?.description ?? objective.description ?? 'Objective'}
                    </span>
                    {result && !done && result.detail ? (
                      <span className="mt-0.5 block text-[10.5px] text-ink-faint">
                        {result.detail}
                      </span>
                    ) : null}
                  </span>
                </li>
              )
            })}
          </ul>
        </section>

        {challenge.hints.length > 0 ? (
          <section>
            <SectionTitle>Hints</SectionTitle>
            <ol className="mb-2 space-y-1">
              {challenge.hints.slice(0, hintsShown).map((hint, index) => (
                <li
                  key={index}
                  className="flex gap-2 rounded-md border border-warn/25 bg-warn/5 px-2.5 py-1.5 text-[11.5px] leading-relaxed text-warn"
                >
                  <Lightbulb size={12} className="mt-0.5 shrink-0" />
                  <span>{hint}</span>
                </li>
              ))}
            </ol>
            {hintsShown < challenge.hints.length ? (
              <Button
                size="sm"
                variant="ghost"
                className="w-full"
                onClick={() => setHintsShown((n) => n + 1)}
              >
                <Lightbulb size={12} />
                Reveal hint {hintsShown + 1} of {challenge.hints.length}
              </Button>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-1.5">
          <SectionTitle>Reset</SectionTitle>
          {challenge.topology ? (
            <Button
              size="sm"
              className="w-full"
              onClick={() => challenge.topology && loadDocument(challenge.topology)}
            >
              <Eraser size={12} />
              Restore the starting network
            </Button>
          ) : (
            <Button size="sm" className="w-full" onClick={reset}>
              <Eraser size={12} />
              Clear the canvas
            </Button>
          )}
        </section>
      </div>

      <div className="space-y-1.5 border-t border-line p-3">
        <Button
          variant="primary"
          className="w-full"
          disabled={checking}
          onClick={() => {
            setBottomTab('terminal')
            void check(challenge.id)
          }}
        >
          {checking ? <Loader2 size={14} className="animate-spin" /> : <Target size={14} />}
          {checking ? 'Checking…' : 'Check objectives'}
        </Button>
        <p className="text-center text-[10.5px] text-ink-faint">
          Objectives are verified by running the real simulation.
        </p>
      </div>
    </div>
  )
}
