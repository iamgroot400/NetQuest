import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button, IconButton } from '@/components/ui/Button'
import { SectionTitle, TextInput } from '@/components/ui/Field'
import { describePort } from '@/lib/services'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, FirewallAction, FirewallRule, RuleProtocol } from '@/types'

const PROTOCOLS: RuleProtocol[] = ['any', 'tcp', 'udp', 'icmp']

const BLANK: FirewallRule = {
  action: 'deny',
  protocol: 'tcp',
  port: null,
  source: 'any',
  destination: 'any',
  description: '',
}

export function FirewallConfig({ device }: { device: Device }) {
  const updateConfig = useTopologyStore((state) => state.updateConfig)
  const links = useTopologyStore((state) => state.links)
  const devices = useTopologyStore((state) => state.devices)
  const [draft, setDraft] = useState<FirewallRule>(BLANK)

  const rules = device.config.firewall_rules
  const policy = device.config.firewall_default_policy
  const hits = device.runtime.firewall_hits ?? {}

  const setRules = (next: FirewallRule[]) =>
    updateConfig(device.id, { firewall_rules: next })

  const add = () => {
    setRules([
      ...rules,
      {
        ...draft,
        source: draft.source.trim() || 'any',
        destination: draft.destination.trim() || 'any',
      },
    ])
    setDraft(BLANK)
  }

  const move = (index: number, delta: number) => {
    const target = index + delta
    if (target < 0 || target >= rules.length) return
    const next = [...rules]
    const [moved] = next.splice(index, 1)
    next.splice(target, 0, moved!)
    setRules(next)
  }

  const describeRulePort = (rule: FirewallRule) => {
    if (rule.port === null) return 'any'
    if (rule.protocol === 'tcp') return describePort('TCP', rule.port)
    if (rule.protocol === 'udp') return describePort('UDP', rule.port)
    return String(rule.port)
  }

  const sides = device.interfaces.map((iface) => {
    const link = links.find(
      (l) => l.a.interface_id === iface.id || l.b.interface_id === iface.id,
    )
    if (!link) return { name: iface.name, peer: 'nothing attached' }
    const far = link.a.interface_id === iface.id ? link.b : link.a
    const peer = devices.find((d) => d.id === far.device_id)
    return { name: iface.name, peer: peer?.name ?? 'unknown' }
  })

  return (
    <div className="space-y-4">
      <p className="rounded-md border border-line bg-panel px-3 py-2.5 text-[11px] leading-relaxed text-ink-dim">
        This firewall sits inline and needs no addresses. Rules are checked from
        the top and the <span className="text-ink">first match wins</span>, so a
        broad deny above a specific allow will quietly defeat it. Replies to
        traffic it has already permitted are allowed back automatically.
      </p>

      <section>
        <SectionTitle>Inline between</SectionTitle>
        <div className="overflow-hidden rounded-md border border-line bg-panel">
          {sides.map((side, index) => (
            <div
              key={side.name}
              className={`flex items-center gap-2 px-2.5 py-1.5 text-[11px] ${
                index > 0 ? 'border-t border-line-soft' : ''
              }`}
            >
              <span className="w-12 font-mono text-ink-dim">{side.name}</span>
              <span className="text-ink-faint">{side.peer}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Default policy</SectionTitle>
        <div className="flex gap-1.5">
          {(['allow', 'deny'] as FirewallAction[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() =>
                updateConfig(device.id, { firewall_default_policy: option })
              }
              className={`flex-1 rounded-md border px-2 py-1.5 text-[11px] font-medium transition-colors ${
                policy === option
                  ? option === 'allow'
                    ? 'border-ok/40 bg-ok/10 text-ok'
                    : 'border-bad/40 bg-bad/10 text-bad'
                  : 'border-line bg-panel text-ink-faint hover:text-ink-dim'
              }`}
            >
              {option === 'allow' ? 'Allow by default' : 'Deny by default'}
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-[10.5px] leading-relaxed text-ink-faint">
          Applied to anything no rule matches
          {hits.default ? ` — used ${hits.default} time(s) so far` : ''}.
        </p>
      </section>

      <section>
        <SectionTitle>Rules</SectionTitle>
        {rules.length === 0 ? (
          <p className="mb-2 rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
            No rules. Everything is decided by the default policy above.
          </p>
        ) : (
          <div className="mb-2 space-y-1">
            {rules.map((rule, index) => (
              <div
                key={index}
                className={`rounded-md border px-2.5 py-1.5 ${
                  rule.action === 'deny'
                    ? 'border-bad/25 bg-bad/5'
                    : 'border-ok/25 bg-ok/5'
                }`}
              >
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="w-4 shrink-0 text-right font-mono text-ink-faint">
                    {index + 1}
                  </span>
                  <span
                    className={`w-11 shrink-0 font-semibold ${
                      rule.action === 'deny' ? 'text-bad' : 'text-ok'
                    }`}
                  >
                    {rule.action}
                  </span>
                  <span className="min-w-0 flex-1 truncate font-mono text-ink-dim">
                    {rule.protocol} {describeRulePort(rule)}
                  </span>
                  <span className="shrink-0 font-mono text-[10px] text-ink-faint tabular-nums">
                    {hits[String(index)] ?? 0}
                  </span>
                  <span className="flex shrink-0 gap-0.5">
                    <IconButton
                      label="Move up"
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp size={11} />
                    </IconButton>
                    <IconButton
                      label="Move down"
                      disabled={index === rules.length - 1}
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown size={11} />
                    </IconButton>
                    <IconButton
                      label={`Delete rule ${index + 1}`}
                      variant="danger"
                      onClick={() => setRules(rules.filter((_, i) => i !== index))}
                    >
                      <Trash2 size={11} />
                    </IconButton>
                  </span>
                </div>
                {(rule.source !== 'any' || rule.destination !== 'any') ? (
                  <p className="mt-0.5 pl-6 font-mono text-[10px] text-ink-faint">
                    {rule.source} → {rule.destination}
                  </p>
                ) : null}
                {rule.description ? (
                  <p className="mt-0.5 pl-6 text-[10px] text-ink-faint">
                    {rule.description}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        )}

        <div className="space-y-2 rounded-md border border-line bg-panel p-2.5">
          <div className="flex gap-1.5">
            <select
              value={draft.action}
              onChange={(event) =>
                setDraft({ ...draft, action: event.target.value as FirewallAction })
              }
              aria-label="Action"
              className="h-9 rounded-md border border-line bg-surface px-1.5 text-xs text-ink"
            >
              <option value="allow">allow</option>
              <option value="deny">deny</option>
            </select>
            <select
              value={draft.protocol}
              onChange={(event) =>
                setDraft({ ...draft, protocol: event.target.value as RuleProtocol })
              }
              aria-label="Protocol"
              className="h-9 rounded-md border border-line bg-surface px-1.5 text-xs text-ink"
            >
              {PROTOCOLS.map((protocol) => (
                <option key={protocol} value={protocol}>
                  {protocol}
                </option>
              ))}
            </select>
            <TextInput
              value={draft.port === null ? '' : String(draft.port)}
              placeholder="Port"
              inputMode="numeric"
              disabled={draft.protocol === 'icmp' || draft.protocol === 'any'}
              onChange={(event) => {
                const digits = event.target.value.replace(/\D/g, '')
                setDraft({ ...draft, port: digits === '' ? null : Number(digits) })
              }}
            />
          </div>

          <div className="flex gap-1.5">
            <TextInput
              value={draft.source}
              placeholder="Source — any or 10.0.1.0/24"
              spellCheck={false}
              onChange={(event) => setDraft({ ...draft, source: event.target.value })}
            />
            <TextInput
              value={draft.destination}
              placeholder="Destination"
              spellCheck={false}
              onChange={(event) =>
                setDraft({ ...draft, destination: event.target.value })
              }
            />
          </div>

          <TextInput
            value={draft.description}
            placeholder="Why this rule exists (optional)"
            onChange={(event) =>
              setDraft({ ...draft, description: event.target.value })
            }
            onKeyDown={(event) => event.key === 'Enter' && add()}
          />

          <Button variant="primary" size="sm" onClick={add} className="w-full">
            <Plus size={13} />
            Add rule
          </Button>
        </div>
      </section>
    </div>
  )
}
