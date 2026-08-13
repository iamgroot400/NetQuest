import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4 } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device } from '@/types'

import { InterfaceEditor } from './InterfaceEditor'

export function HostConfig({ device }: { device: Device }) {
  const setGateway = useTopologyStore((state) => state.setGateway)
  const [gateway, setGatewayDraft] = useState(device.config.gateway ?? '')

  useEffect(() => {
    setGatewayDraft(device.config.gateway ?? '')
  }, [device.id, device.config.gateway])

  const error =
    gateway !== '' && !isValidIpv4(gateway) ? 'Not a valid IPv4 address.' : null
  const dirty = (device.config.gateway ?? '') !== gateway
  const canApply = dirty && !error

  const apply = () => {
    if (!canApply) return
    setGateway(device.id, gateway.trim() || null)
  }

  const arpEntries = Object.entries(device.runtime.arp_table)

  return (
    <div className="space-y-4">
      <section>
        <SectionTitle>Network configuration</SectionTitle>
        <div className="space-y-3">
          {device.interfaces.map((iface) => (
            <InterfaceEditor key={iface.id} device={device} iface={iface} />
          ))}

          <div className="rounded-md border border-line bg-panel p-3">
            <Field
              label="Default gateway"
              error={error}
              hint={<span className="text-ink-faint">for other subnets</span>}
            >
              <TextInput
                value={gateway}
                invalid={!!error}
                placeholder="192.168.1.1"
                spellCheck={false}
                onChange={(event) => setGatewayDraft(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && apply()}
              />
            </Field>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-faint">
              Anything outside this host&apos;s own subnet is handed here. Leave it
              empty and the host can only reach its local network.
            </p>
            <Button
              variant={canApply ? 'primary' : 'default'}
              size="sm"
              disabled={!canApply}
              onClick={apply}
              className="mt-2.5 w-full"
            >
              {dirty ? 'Apply' : 'Applied'}
            </Button>
          </div>
        </div>
      </section>

      <section>
        <SectionTitle>ARP cache</SectionTitle>
        {arpEntries.length === 0 ? (
          <p className="rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
            Empty. This host learns hardware addresses the first time it needs to
            send something — run a ping and watch it fill.
          </p>
        ) : (
          <table className="w-full overflow-hidden rounded-md border border-line bg-panel text-[11px]">
            <thead>
              <tr className="border-b border-line text-left text-ink-faint">
                <th className="px-2.5 py-1.5 font-medium">Address</th>
                <th className="px-2.5 py-1.5 font-medium">MAC</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-dim">
              {arpEntries.map(([ip, mac]) => (
                <tr key={ip} className="border-t border-line-soft">
                  <td className="px-2.5 py-1.5">{ip}</td>
                  <td className="px-2.5 py-1.5">{mac}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
