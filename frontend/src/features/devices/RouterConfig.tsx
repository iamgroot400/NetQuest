import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button, IconButton } from '@/components/ui/Button'
import { SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4, isValidNetmask } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, StaticRoute } from '@/types'

import { InterfaceEditor } from './InterfaceEditor'

const BLANK: StaticRoute = { destination: '', netmask: '255.255.255.0', gateway: '' }

export function RouterConfig({ device }: { device: Device }) {
  const setStaticRoutes = useTopologyStore((state) => state.setStaticRoutes)
  const [draft, setDraft] = useState<StaticRoute>(BLANK)

  const routes = device.config.static_routes
  const draftValid =
    isValidIpv4(draft.destination) &&
    isValidNetmask(draft.netmask) &&
    isValidIpv4(draft.gateway)

  const addRoute = () => {
    if (!draftValid) return
    setStaticRoutes(device.id, [...routes, draft])
    setDraft(BLANK)
  }

  const removeRoute = (index: number) =>
    setStaticRoutes(
      device.id,
      routes.filter((_, i) => i !== index),
    )

  return (
    <div className="space-y-4">
      <section>
        <SectionTitle>Interfaces</SectionTitle>
        <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
          Each addressed interface becomes a connected route automatically, and
          serves as the default gateway for the hosts on that subnet.
        </p>
        <div className="space-y-3">
          {device.interfaces.map((iface) => (
            <InterfaceEditor key={iface.id} device={device} iface={iface} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Static routes</SectionTitle>
        <p className="mb-2 text-[11px] leading-relaxed text-ink-faint">
          For networks this router is not attached to. The next hop must sit on one
          of its own subnets.
        </p>

        {routes.length > 0 ? (
          <div className="mb-2 overflow-hidden rounded-md border border-line bg-panel">
            {routes.map((route, index) => (
              <div
                key={`${route.destination}-${route.netmask}-${index}`}
                className={`flex items-center gap-2 px-2.5 py-1.5 font-mono text-[11px] ${
                  index > 0 ? 'border-t border-line-soft' : ''
                }`}
              >
                <span className="min-w-0 flex-1 truncate text-ink-dim">
                  {route.destination} / {route.netmask}
                </span>
                <span className="shrink-0 text-ink-faint">via {route.gateway}</span>
                <IconButton
                  label={`Delete route to ${route.destination}`}
                  variant="danger"
                  onClick={() => removeRoute(index)}
                >
                  <Trash2 size={12} />
                </IconButton>
              </div>
            ))}
          </div>
        ) : null}

        <div className="space-y-2 rounded-md border border-line bg-panel p-2.5">
          <TextInput
            value={draft.destination}
            placeholder="Destination network — 192.168.20.0"
            spellCheck={false}
            invalid={draft.destination !== '' && !isValidIpv4(draft.destination)}
            onChange={(event) => setDraft({ ...draft, destination: event.target.value })}
          />
          <TextInput
            value={draft.netmask}
            placeholder="Netmask — 255.255.255.0"
            spellCheck={false}
            invalid={draft.netmask !== '' && !isValidNetmask(draft.netmask)}
            onChange={(event) => setDraft({ ...draft, netmask: event.target.value })}
          />
          <TextInput
            value={draft.gateway}
            placeholder="Next hop — 10.0.0.2"
            spellCheck={false}
            invalid={draft.gateway !== '' && !isValidIpv4(draft.gateway)}
            onChange={(event) => setDraft({ ...draft, gateway: event.target.value })}
            onKeyDown={(event) => event.key === 'Enter' && addRoute()}
          />
          <Button
            variant={draftValid ? 'primary' : 'default'}
            size="sm"
            disabled={!draftValid}
            onClick={addRoute}
            className="w-full"
          >
            <Plus size={13} />
            Add route
          </Button>
        </div>
      </section>
    </div>
  )
}
