import { Trophy, Unlock } from 'lucide-react'
import { useEffect } from 'react'

import { Button } from '@/components/ui/Button'
import { useProgressStore } from '@/stores/progressStore'

export function MissionComplete() {
  const award = useProgressStore((state) => state.award)
  const dismiss = useProgressStore((state) => state.dismissAward)

  useEffect(() => {
    if (!award) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [award, dismiss])

  if (!award) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mission-complete-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-base/80 p-4 backdrop-blur-sm"
      onClick={dismiss}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-ok/30 bg-panel p-6 text-center shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ok/10 text-ok">
          <Trophy size={22} />
        </span>

        <h2
          id="mission-complete-title"
          className="text-[11px] font-semibold tracking-widest text-ok uppercase"
        >
          Mission complete
        </h2>
        <p className="mt-1 text-lg font-semibold text-ink">{award.challengeName}</p>

        <p className="mt-4 font-mono text-2xl font-bold text-accent">+{award.xp} XP</p>
        <p className="mt-1 text-xs text-ink-faint">
          Networking XP: <span className="text-ink-dim">{award.totalXp}</span>
        </p>

        {award.levelUp ? (
          <p className="mt-4 rounded-md border border-accent/30 bg-accent/10 px-3 py-2 text-xs text-accent">
            Level {award.levelUp.level} reached — {award.levelUp.name}
          </p>
        ) : null}

        {award.unlocked.length > 0 ? (
          <div className="mt-3 space-y-1">
            {award.unlocked.map((name) => (
              <p
                key={name}
                className="flex items-center justify-center gap-1.5 text-xs text-ink-dim"
              >
                <Unlock size={12} className="text-ok" />
                Unlocked: {name}
              </p>
            ))}
          </div>
        ) : null}

        <Button variant="primary" className="mt-6 w-full" onClick={dismiss} autoFocus>
          Continue
        </Button>
      </div>
    </div>
  )
}
