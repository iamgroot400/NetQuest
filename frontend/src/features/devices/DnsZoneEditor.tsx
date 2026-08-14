import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button, IconButton } from '@/components/ui/Button'
import { SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4 } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, DnsRecord, DnsRecordType } from '@/types'

const TYPES: DnsRecordType[] = ['A', 'CNAME', 'MX']

const BLANK: DnsRecord = { name: '', type: 'A', value: '', priority: 10 }

const HINTS: Record<DnsRecordType, string> = {
  A: 'Points a name straight at an address.',
  CNAME: 'Points a name at another name, which is then resolved in turn.',
  MX: 'Names the mail server for a domain, lowest priority first.',
}

/** The zone this server answers from. Edits change what lookups return. */
export function DnsZoneEditor({ device }: { device: Device }) {
  const updateConfig = useTopologyStore((state) => state.updateConfig)
  const [draft, setDraft] = useState<DnsRecord>(BLANK)

  const records = device.config.dns_records
  const valueIsAddress = draft.type === 'A'
  const draftValid =
    draft.name.trim() !== '' &&
    draft.value.trim() !== '' &&
    (!valueIsAddress || isValidIpv4(draft.value.trim()))

  const add = () => {
    if (!draftValid) return
    updateConfig(device.id, {
      dns_records: [
        ...records,
        {
          ...draft,
          name: draft.name.trim().toLowerCase(),
          value: draft.value.trim(),
        },
      ],
    })
    setDraft({ ...BLANK, type: draft.type })
  }

  const remove = (index: number) =>
    updateConfig(device.id, {
      dns_records: records.filter((_, i) => i !== index),
    })

  return (
    <section>
      <SectionTitle>DNS zone</SectionTitle>
      <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
        {records.length === 0
          ? 'Empty. This server will answer every lookup with NXDOMAIN until you add a record.'
          : 'Clients that point at this server resolve names from these records.'}
      </p>

      {records.length > 0 ? (
        <div className="mb-2 overflow-hidden rounded-md border border-line bg-panel">
          {records.map((record, index) => (
            <div
              key={`${record.name}-${record.type}-${index}`}
              className={`flex items-center gap-2 px-2.5 py-1.5 font-mono text-[11px] ${
                index > 0 ? 'border-t border-line-soft' : ''
              }`}
            >
              <span className="w-12 shrink-0 text-accent">{record.type}</span>
              <span className="min-w-0 flex-1 truncate text-ink-dim" title={record.name}>
                {record.name}
              </span>
              <span className="shrink-0 text-ink-faint">→</span>
              <span
                className="min-w-0 flex-1 truncate text-right text-ink-dim"
                title={record.value}
              >
                {record.type === 'MX' ? `${record.priority} ${record.value}` : record.value}
              </span>
              <IconButton
                label={`Delete ${record.type} record for ${record.name}`}
                variant="danger"
                onClick={() => remove(index)}
              >
                <Trash2 size={12} />
              </IconButton>
            </div>
          ))}
        </div>
      ) : null}

      <div className="space-y-2 rounded-md border border-line bg-panel p-2.5">
        <div className="flex gap-1.5">
          <select
            value={draft.type}
            onChange={(event) =>
              setDraft({ ...draft, type: event.target.value as DnsRecordType })
            }
            aria-label="Record type"
            className="h-9 rounded-md border border-line bg-surface px-1.5 font-mono text-xs text-ink"
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <TextInput
            value={draft.name}
            placeholder="web.netquest.local"
            spellCheck={false}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
        </div>

        <TextInput
          value={draft.value}
          placeholder={valueIsAddress ? '10.0.2.10' : 'web.netquest.local'}
          spellCheck={false}
          invalid={
            valueIsAddress && draft.value !== '' && !isValidIpv4(draft.value.trim())
          }
          onChange={(event) => setDraft({ ...draft, value: event.target.value })}
          onKeyDown={(event) => event.key === 'Enter' && add()}
        />

        {draft.type === 'MX' ? (
          <TextInput
            value={String(draft.priority)}
            placeholder="Priority — 10"
            inputMode="numeric"
            onChange={(event) =>
              setDraft({ ...draft, priority: Number(event.target.value) || 0 })
            }
          />
        ) : null}

        <p className="text-[10.5px] leading-relaxed text-ink-faint">
          {HINTS[draft.type]}
        </p>

        <Button
          variant={draftValid ? 'primary' : 'default'}
          size="sm"
          disabled={!draftValid}
          onClick={add}
          className="w-full"
        >
          <Plus size={13} />
          Add record
        </Button>
      </div>
    </section>
  )
}
