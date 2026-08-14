import { Check, Lock, Star } from 'lucide-react'
import { useEffect } from 'react'

import { SectionTitle } from '@/components/ui/Field'
import { isLocked, useChallengeStore } from '@/stores/challengeStore'
import { useProgressStore } from '@/stores/progressStore'
import { useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'
import type { Challenge, ChallengeCategory } from '@/types'

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  beginner: 'Getting started',
  switching: 'Switching',
  routing: 'Routing',
  services: 'DNS & DHCP',
  security: 'Firewalls, NAT & VPN',
  troubleshooting: 'Troubleshooting',
}

const CATEGORY_ORDER: ChallengeCategory[] = [
  'beginner',
  'switching',
  'routing',
  'services',
  'security',
  'troubleshooting',
]

export function ChallengeList() {
  const { challenges, loading, error, load } = useChallengeStore()
  const completed = useProgressStore((state) => state.completed)
  const activeId = useProgressStore((state) => state.activeChallengeId)
  const setActiveChallenge = useProgressStore((state) => state.setActiveChallenge)

  const loadDocument = useTopologyStore((state) => state.loadDocument)
  const deviceCount = useTopologyStore((state) => state.devices.length)
  const setRightTab = useUiStore((state) => state.setRightTab)
  const notify = useUiStore((state) => state.notify)

  useEffect(() => {
    void load()
  }, [load])

  const start = (challenge: Challenge) => {
    if (isLocked(challenge, completed)) {
      notify('Finish the missions this one builds on first.', 'info')
      return
    }
    if (challenge.topology) {
      const confirmed =
        deviceCount === 0 ||
        window.confirm(
          `"${challenge.name}" comes with its own network. Replace what is on the canvas?`,
        )
      if (!confirmed) return
      loadDocument(challenge.topology)
    }
    setActiveChallenge(challenge.id)
    setRightTab('mission')
  }

  if (loading && challenges.length === 0) {
    return <p className="px-3 py-4 text-[11px] text-ink-faint">Loading missions…</p>
  }

  if (error) {
    return (
      <div className="px-3 py-4">
        <p className="text-[11px] leading-relaxed text-bad">{error}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-2 text-[11px] text-accent underline"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="p-3">
      <SectionTitle>Missions</SectionTitle>
      <div className="space-y-3">
        {CATEGORY_ORDER.map((category) => {
          const group = challenges.filter((c) => c.category === category)
          if (!group.length) return null
          return (
            <div key={category}>
              <h4 className="mb-1 text-[10px] font-medium tracking-wide text-ink-faint">
                {CATEGORY_LABEL[category]}
              </h4>
              <ul className="space-y-1">
                {group.map((challenge) => {
                  const done = completed.includes(challenge.id)
                  const locked = isLocked(challenge, completed)
                  const active = challenge.id === activeId
                  return (
                    <li key={challenge.id}>
                      <button
                        type="button"
                        onClick={() => start(challenge)}
                        aria-current={active}
                        className={`flex w-full items-start gap-2 rounded-md border px-2 py-1.5 text-left transition-colors ${
                          active
                            ? 'border-accent/50 bg-accent/10'
                            : 'border-line bg-panel hover:border-ink-faint hover:bg-raised'
                        } ${locked ? 'opacity-55' : ''}`}
                      >
                        <span className="mt-0.5 shrink-0">
                          {done ? (
                            <Check size={13} className="text-ok" />
                          ) : locked ? (
                            <Lock size={12} className="text-ink-faint" />
                          ) : (
                            <Star size={12} className="text-ink-faint" />
                          )}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[12px] font-medium text-ink">
                            {challenge.name}
                          </span>
                          <span className="block text-[10.5px] text-ink-faint">
                            {'★'.repeat(challenge.difficulty)} · {challenge.xp} XP
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
