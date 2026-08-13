import type { ReactNode } from 'react'

export interface TabDefinition<T extends string> {
  id: T
  label: string
  badge?: number
  icon?: ReactNode
}

interface TabsProps<T extends string> {
  tabs: TabDefinition<T>[]
  active: T
  onChange: (id: T) => void
  right?: ReactNode
}

export function Tabs<T extends string>({ tabs, active, onChange, right }: TabsProps<T>) {
  return (
    <div className="flex h-9 shrink-0 items-stretch justify-between border-b border-line bg-surface">
      <div role="tablist" className="flex items-stretch">
        {tabs.map((tab) => {
          const selected = tab.id === active
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(tab.id)}
              className={`flex items-center gap-1.5 border-b-2 px-3 text-xs font-medium transition-colors ${
                selected
                  ? 'border-accent text-ink'
                  : 'border-transparent text-ink-faint hover:text-ink-dim'
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.badge ? (
                <span className="rounded bg-raised px-1 text-[10px] text-ink-dim tabular-nums">
                  {tab.badge}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
      {right ? <div className="flex items-center gap-1 pr-2">{right}</div> : null}
    </div>
  )
}
