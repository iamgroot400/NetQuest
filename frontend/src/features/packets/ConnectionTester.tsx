import { ArrowRight, Ban, CircleCheck, Loader2, Play, ShieldOff } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { ApiError, api } from '@/lib/api'
import { WELL_KNOWN, describePort } from '@/lib/services'
import { useSimulationStore } from '@/stores/simulationStore'
import { toDocument, useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'
import type { ConnectionOutcome, ConnectionResult, TransportProtocol } from '@/types'

const OUTCOME_STYLE: Record<
  ConnectionOutcome,
  { label: string; className: string; icon: typeof CircleCheck; hint: string }
> = {
  open: {
    label: 'Open',
    className: 'border-ok/30 bg-ok/10 text-ok',
    icon: CircleCheck,
    hint: 'Something is listening and the whole path works.',
  },
  refused: {
    label: 'Refused',
    className: 'border-warn/30 bg-warn/10 text-warn',
    icon: Ban,
    hint: 'The host is reachable and answered — nothing is listening on that port.',
  },
  filtered: {
    label: 'Filtered',
    className: 'border-bad/30 bg-bad/10 text-bad',
    icon: ShieldOff,
    hint: 'Nothing came back at all. Something in the middle dropped it silently.',
  },
  unreachable: {
    label: 'Unreachable',
    className: 'border-bad/30 bg-bad/10 text-bad',
    icon: Ban,
    hint: 'A router said explicitly that it could not get there.',
  },
  'no-route': {
    label: 'No route',
    className: 'border-bad/30 bg-bad/10 text-bad',
    icon: Ban,
    hint: 'The packet never even left the source device.',
  },
  'dns-failure': {
    label: 'Name did not resolve',
    className: 'border-bad/30 bg-bad/10 text-bad',
    icon: Ban,
    hint: 'This is a DNS problem, not a connectivity one.',
  },
  'no-source-address': {
    label: 'No address',
    className: 'border-bad/30 bg-bad/10 text-bad',
    icon: Ban,
    hint: 'The source device has no IPv4 address to send from.',
  },
}

export function ConnectionTester() {
  const devices = useTopologyStore((state) => state.devices)
  const selectedDeviceId = useTopologyStore((state) => state.selectedDeviceId)
  const applyDeviceState = useTopologyStore((state) => state.applyDeviceState)
  const notify = useUiStore((state) => state.notify)

  const hosts = devices.filter((d) => d.type === 'pc' || d.type === 'server')

  const [source, setSource] = useState<string>('')
  const [destination, setDestination] = useState('')
  const [port, setPort] = useState('80')
  const [protocol, setProtocol] = useState<TransportProtocol>('TCP')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ConnectionResult | null>(null)

  const effectiveSource =
    hosts.find((h) => h.id === source)?.id ??
    hosts.find((h) => h.id === selectedDeviceId)?.id ??
    hosts[0]?.id ??
    ''

  if (hosts.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="text-xs leading-relaxed text-ink-faint">
          Add a PC or a server to the canvas — a connection has to start somewhere.
        </p>
      </div>
    )
  }

  const run = async () => {
    const portNumber = Number(port)
    if (!effectiveSource || !destination.trim() || !Number.isInteger(portNumber)) return

    setRunning(true)
    try {
      const response = await api.testConnection(
        toDocument(),
        effectiveSource,
        destination.trim(),
        portNumber,
        protocol,
      )
      setResult(response)
      applyDeviceState(response.device_state)
      // Feed the trace to the animator so the canvas shows the same attempt.
      useSimulationStore.getState().load(response.events, response.packets)
    } catch (error) {
      notify(
        error instanceof ApiError ? error.message : 'The test could not be run.',
        'error',
      )
    } finally {
      setRunning(false)
    }
  }

  const style = result ? OUTCOME_STYLE[result.outcome] : null
  const OutcomeIcon = style?.icon

  return (
    <div className="flex h-full min-h-0">
      <div className="w-[300px] shrink-0 space-y-2.5 overflow-y-auto border-r border-line-soft p-3">
        <SectionTitle>Test a connection</SectionTitle>

        <Field label="From">
          <select
            value={effectiveSource}
            onChange={(event) => setSource(event.target.value)}
            className="h-9 w-full rounded-md border border-line bg-surface px-2 font-mono text-sm text-ink"
          >
            {hosts.map((host) => (
              <option key={host.id} value={host.id}>
                {host.name}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="To"
          hint={<span className="text-ink-faint">address or name</span>}
        >
          <TextInput
            value={destination}
            placeholder="web.netquest.local"
            spellCheck={false}
            onChange={(event) => setDestination(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && void run()}
          />
        </Field>

        <div className="flex gap-1.5">
          <span className="w-20 shrink-0">
            <Field label="Protocol">
              <select
                value={protocol}
                onChange={(event) =>
                  setProtocol(event.target.value as TransportProtocol)
                }
                className="h-9 w-full rounded-md border border-line bg-surface px-1.5 font-mono text-sm text-ink"
              >
                <option value="TCP">TCP</option>
                <option value="UDP">UDP</option>
              </select>
            </Field>
          </span>
          <span className="flex-1">
            <Field label="Port">
              <TextInput
                value={port}
                inputMode="numeric"
                onChange={(event) => setPort(event.target.value.replace(/\D/g, ''))}
                onKeyDown={(event) => event.key === 'Enter' && void run()}
              />
            </Field>
          </span>
        </div>

        <div className="flex flex-wrap gap-1">
          {WELL_KNOWN.slice(0, 6).map((service) => (
            <button
              key={`${service.protocol}-${service.port}`}
              type="button"
              onClick={() => {
                setPort(String(service.port))
                setProtocol(service.protocol)
              }}
              className="rounded border border-line bg-panel px-1.5 py-0.5 font-mono text-[10px] text-ink-faint transition-colors hover:border-ink-faint hover:text-ink-dim"
            >
              {service.name}
            </button>
          ))}
        </div>

        <Button
          variant="primary"
          className="w-full"
          disabled={running || !destination.trim() || !port}
          onClick={() => void run()}
        >
          {running ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          {running ? 'Testing…' : 'Test connection'}
        </Button>

        <p className="text-[10.5px] leading-relaxed text-ink-faint">
          Sends a real packet through the simulated network and reports exactly
          what came back.
        </p>
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-3">
        {!result ? (
          <p className="px-1 py-6 text-center text-xs leading-relaxed text-ink-faint">
            No test run yet. The result will show whether the port answered, and
            if not, exactly where the traffic stopped.
          </p>
        ) : (
          <div className="space-y-3">
            <div
              className={`flex items-start gap-2 rounded-md border px-3 py-2.5 ${style!.className}`}
            >
              {OutcomeIcon ? <OutcomeIcon size={15} className="mt-0.5 shrink-0" /> : null}
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold">{style!.label}</span>
                <span className="block text-[11px] leading-relaxed opacity-90">
                  {result.detail}
                </span>
              </span>
            </div>

            <p className="text-[11px] leading-relaxed text-ink-faint">
              {style!.hint}
            </p>

            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-md border border-line bg-panel p-2.5 text-[11px]">
              <dt className="text-ink-faint">Target</dt>
              <dd className="truncate text-right font-mono text-ink-dim">
                {result.target}
              </dd>
              {result.resolved_ip && result.resolved_ip !== result.target ? (
                <>
                  <dt className="text-ink-faint">Resolved to</dt>
                  <dd className="truncate text-right font-mono text-ink-dim">
                    {result.resolved_ip}
                  </dd>
                </>
              ) : null}
              <dt className="text-ink-faint">Port</dt>
              <dd className="text-right font-mono text-ink-dim">
                {result.port !== null
                  ? describePort(result.protocol, result.port)
                  : '—'}
              </dd>
            </dl>

            {result.path.length > 0 ? (
              <section>
                <SectionTitle>Path taken</SectionTitle>
                <ol className="space-y-1">
                  {result.path.map((hop, index) => {
                    const stopped = hop === result.blocked_at
                    return (
                      <li
                        key={`${hop}-${index}`}
                        className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[11px] ${
                          stopped
                            ? 'border-bad/30 bg-bad/5 text-bad'
                            : 'border-line bg-panel text-ink-dim'
                        }`}
                      >
                        <span className="w-4 shrink-0 text-right font-mono text-ink-faint">
                          {index + 1}
                        </span>
                        <span className="font-medium">{hop}</span>
                        {stopped ? (
                          <span className="ml-auto text-[10px]">stopped here</span>
                        ) : index === result.path.length - 1 && result.reachable ? (
                          <span className="ml-auto text-[10px] text-ok">arrived</span>
                        ) : (
                          <ArrowRight size={11} className="ml-auto text-ink-faint" />
                        )}
                      </li>
                    )
                  })}
                </ol>
              </section>
            ) : null}

            {result.blocked_reason ? (
              <section>
                <SectionTitle>Why it stopped</SectionTitle>
                <p className="rounded-md border border-line bg-panel px-2.5 py-2 font-mono text-[11px] leading-relaxed text-ink-dim">
                  {result.blocked_reason}
                </p>
              </section>
            ) : null}

            {result.dns_detail ? (
              <section>
                <SectionTitle>DNS said</SectionTitle>
                <p className="rounded-md border border-line bg-panel px-2.5 py-2 font-mono text-[11px] leading-relaxed text-ink-dim">
                  {result.dns_detail}
                </p>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
