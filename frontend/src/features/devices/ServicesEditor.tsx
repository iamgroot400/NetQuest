import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button, IconButton } from '@/components/ui/Button'
import { SectionTitle, TextInput } from '@/components/ui/Field'
import { WELL_KNOWN, describePort, findService } from '@/lib/services'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, Service, TransportProtocol } from '@/types'

/**
 * Which ports this device listens on. A disabled service closes the port for
 * real: connections to it are then refused rather than accepted.
 */
export function ServicesEditor({ device }: { device: Device }) {
  const updateConfig = useTopologyStore((state) => state.updateConfig)
  const [customPort, setCustomPort] = useState('')
  const [customProtocol, setCustomProtocol] = useState<TransportProtocol>('TCP')

  const services = device.config.services

  const toggle = (name: string, protocol: TransportProtocol, port: number) => {
    const existing = findService(services, protocol, port)
    if (existing) {
      updateConfig(device.id, {
        services: services.map((s) =>
          s === existing ? { ...s, enabled: !s.enabled } : s,
        ),
      })
      return
    }
    updateConfig(device.id, {
      services: [...services, { name, protocol, port, enabled: true }],
    })
  }

  const remove = (service: Service) =>
    updateConfig(device.id, { services: services.filter((s) => s !== service) })

  const addCustom = () => {
    const port = Number(customPort)
    if (!Number.isInteger(port) || port < 1 || port > 65535) return
    if (findService(services, customProtocol, port)) return
    updateConfig(device.id, {
      services: [
        ...services,
        { name: `Port ${port}`, protocol: customProtocol, port, enabled: true },
      ],
    })
    setCustomPort('')
  }

  const custom = services.filter(
    (s) => !WELL_KNOWN.some((k) => k.protocol === s.protocol && k.port === s.port),
  )

  return (
    <section>
      <SectionTitle>Services</SectionTitle>
      <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
        A port only answers when something is listening on it. Turn a service off
        and connections to it are refused.
      </p>

      <div className="overflow-hidden rounded-md border border-line bg-panel">
        {WELL_KNOWN.map((known, index) => {
          const existing = findService(services, known.protocol, known.port)
          const on = !!existing?.enabled
          return (
            <label
              key={`${known.protocol}-${known.port}`}
              title={known.description}
              className={`flex cursor-pointer items-center gap-2 px-2.5 py-1.5 text-[11px] transition-colors hover:bg-raised ${
                index > 0 ? 'border-t border-line-soft' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggle(known.name, known.protocol, known.port)}
                className="h-3 w-3 accent-[var(--color-accent)]"
              />
              <span className={`w-14 font-medium ${on ? 'text-ink' : 'text-ink-faint'}`}>
                {known.name}
              </span>
              <span className="flex-1 font-mono text-ink-faint">
                {known.port}/{known.protocol.toLowerCase()}
              </span>
              <span className={on ? 'text-ok' : 'text-ink-faint'}>
                {on ? 'listening' : 'closed'}
              </span>
            </label>
          )
        })}
      </div>

      {custom.length > 0 ? (
        <div className="mt-2 overflow-hidden rounded-md border border-line bg-panel">
          {custom.map((service, index) => (
            <div
              key={`${service.protocol}-${service.port}`}
              className={`flex items-center gap-2 px-2.5 py-1.5 text-[11px] ${
                index > 0 ? 'border-t border-line-soft' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={service.enabled}
                onChange={() => toggle(service.name, service.protocol, service.port)}
                className="h-3 w-3 accent-[var(--color-accent)]"
              />
              <span className="flex-1 font-mono text-ink-dim">
                {describePort(service.protocol, service.port)}
              </span>
              <IconButton
                label={`Remove port ${service.port}`}
                variant="danger"
                onClick={() => remove(service)}
              >
                <Trash2 size={12} />
              </IconButton>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-2 flex gap-1.5">
        <select
          value={customProtocol}
          onChange={(event) =>
            setCustomProtocol(event.target.value as TransportProtocol)
          }
          aria-label="Protocol"
          className="h-9 rounded-md border border-line bg-surface px-1.5 font-mono text-xs text-ink"
        >
          <option value="TCP">TCP</option>
          <option value="UDP">UDP</option>
        </select>
        <TextInput
          value={customPort}
          placeholder="Custom port"
          inputMode="numeric"
          onChange={(event) => setCustomPort(event.target.value.replace(/\D/g, ''))}
          onKeyDown={(event) => event.key === 'Enter' && addCustom()}
        />
        <Button size="md" disabled={!customPort} onClick={addCustom}>
          <Plus size={13} />
        </Button>
      </div>
    </section>
  )
}
