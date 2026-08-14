import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4, isValidNetmask } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, DhcpPool } from '@/types'

const DEFAULT_POOL: DhcpPool = {
  start: '192.168.1.100',
  end: '192.168.1.150',
  netmask: '255.255.255.0',
  gateway: null,
  dns: null,
  lease_seconds: 86400,
  enabled: true,
}

/** What this server hands out. Every field lands on the client for real. */
export function DhcpPoolEditor({ device }: { device: Device }) {
  const updateConfig = useTopologyStore((state) => state.updateConfig)
  const pool = device.config.dhcp_pool
  const [draft, setDraft] = useState<DhcpPool>(pool ?? DEFAULT_POOL)

  useEffect(() => {
    if (pool) setDraft(pool)
  }, [pool])

  const leases = Object.entries(device.runtime.dhcp_leases ?? {})

  if (!pool) {
    return (
      <section>
        <SectionTitle>DHCP pool</SectionTitle>
        <p className="mb-2 rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
          No pool configured, so this server has nothing to hand out. Add one and
          clients that ask will be given an address, mask, gateway and DNS server.
        </p>
        <Button
          size="sm"
          className="w-full"
          onClick={() => updateConfig(device.id, { dhcp_pool: DEFAULT_POOL })}
        >
          Add a pool
        </Button>
      </section>
    )
  }

  const errors = {
    start: draft.start && !isValidIpv4(draft.start) ? 'Not a valid address.' : null,
    end: draft.end && !isValidIpv4(draft.end) ? 'Not a valid address.' : null,
    netmask:
      draft.netmask && !isValidNetmask(draft.netmask) ? 'Not a valid mask.' : null,
    gateway:
      draft.gateway && !isValidIpv4(draft.gateway) ? 'Not a valid address.' : null,
    dns: draft.dns && !isValidIpv4(draft.dns) ? 'Not a valid address.' : null,
  }
  const valid = Object.values(errors).every((e) => e === null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(pool)

  const apply = () => {
    if (!valid || !dirty) return
    updateConfig(device.id, {
      dhcp_pool: {
        ...draft,
        gateway: draft.gateway?.trim() || null,
        dns: draft.dns?.trim() || null,
      },
    })
  }

  return (
    <section>
      <SectionTitle>DHCP pool</SectionTitle>

      <div className="space-y-2.5 rounded-md border border-line bg-panel p-3">
        <label className="flex items-center gap-2 text-[11px] text-ink-dim">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
            className="h-3 w-3 accent-[var(--color-accent)]"
          />
          Pool enabled
        </label>

        <div className="grid grid-cols-2 gap-2">
          <Field label="First address" error={errors.start}>
            <TextInput
              value={draft.start}
              invalid={!!errors.start}
              spellCheck={false}
              onChange={(event) => setDraft({ ...draft, start: event.target.value })}
            />
          </Field>
          <Field label="Last address" error={errors.end}>
            <TextInput
              value={draft.end}
              invalid={!!errors.end}
              spellCheck={false}
              onChange={(event) => setDraft({ ...draft, end: event.target.value })}
            />
          </Field>
        </div>

        <Field label="Subnet mask" error={errors.netmask}>
          <TextInput
            value={draft.netmask}
            invalid={!!errors.netmask}
            spellCheck={false}
            onChange={(event) => setDraft({ ...draft, netmask: event.target.value })}
          />
        </Field>

        <Field
          label="Gateway given to clients"
          error={errors.gateway}
          hint={<span className="text-ink-faint">optional</span>}
        >
          <TextInput
            value={draft.gateway ?? ''}
            invalid={!!errors.gateway}
            placeholder="192.168.1.1"
            spellCheck={false}
            onChange={(event) => setDraft({ ...draft, gateway: event.target.value })}
          />
        </Field>

        <Field
          label="DNS server given to clients"
          error={errors.dns}
          hint={<span className="text-ink-faint">optional</span>}
        >
          <TextInput
            value={draft.dns ?? ''}
            invalid={!!errors.dns}
            placeholder="192.168.1.53"
            spellCheck={false}
            onChange={(event) => setDraft({ ...draft, dns: event.target.value })}
            onKeyDown={(event) => event.key === 'Enter' && apply()}
          />
        </Field>

        <Button
          variant={valid && dirty ? 'primary' : 'default'}
          size="sm"
          disabled={!valid || !dirty}
          onClick={apply}
          className="w-full"
        >
          {dirty ? 'Apply' : 'Applied'}
        </Button>
      </div>

      <div className="mt-2">
        <SectionTitle>Leases</SectionTitle>
        {leases.length === 0 ? (
          <p className="rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
            None yet. Set a client to obtain its address automatically, then run{' '}
            <span className="font-mono text-ink-dim">dhcp renew</span> on it.
          </p>
        ) : (
          <table className="w-full overflow-hidden rounded-md border border-line bg-panel text-[11px]">
            <thead>
              <tr className="border-b border-line text-left text-ink-faint">
                <th className="px-2.5 py-1.5 font-medium">Client MAC</th>
                <th className="px-2.5 py-1.5 font-medium">Address</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-dim">
              {leases.map(([mac, ip]) => (
                <tr key={mac} className="border-t border-line-soft">
                  <td className="px-2.5 py-1.5">{mac}</td>
                  <td className="px-2.5 py-1.5">{ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
