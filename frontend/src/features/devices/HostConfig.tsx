import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4 } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device } from '@/types'

import { DhcpPoolEditor } from './DhcpPoolEditor'
import { DnsZoneEditor } from './DnsZoneEditor'
import { InterfaceEditor } from './InterfaceEditor'
import { ServicesEditor } from './ServicesEditor'
import { VpnEditor } from './VpnEditor'

export function HostConfig({ device }: { device: Device }) {
  const setGateway = useTopologyStore((state) => state.setGateway)
  const updateConfig = useTopologyStore((state) => state.updateConfig)

  const [gateway, setGatewayDraft] = useState(device.config.gateway ?? '')
  const [dnsServer, setDnsServerDraft] = useState(device.config.dns_server ?? '')

  useEffect(() => {
    setGatewayDraft(device.config.gateway ?? '')
    setDnsServerDraft(device.config.dns_server ?? '')
  }, [device.id, device.config.gateway, device.config.dns_server])

  const gatewayError =
    gateway !== '' && !isValidIpv4(gateway) ? 'Not a valid IPv4 address.' : null
  const dnsError =
    dnsServer !== '' && !isValidIpv4(dnsServer) ? 'Not a valid IPv4 address.' : null

  const gatewayDirty = (device.config.gateway ?? '') !== gateway
  const dnsDirty = (device.config.dns_server ?? '') !== dnsServer
  const canApply = (gatewayDirty || dnsDirty) && !gatewayError && !dnsError

  const apply = () => {
    if (!canApply) return
    if (gatewayDirty) setGateway(device.id, gateway.trim() || null)
    if (dnsDirty) updateConfig(device.id, { dns_server: dnsServer.trim() || null })
  }

  const arpEntries = Object.entries(device.runtime.arp_table)
  const dnsCache = Object.entries(device.runtime.dns_cache ?? {})
  const listening = device.config.services.filter((s) => s.enabled)
  const servesDns = listening.some((s) => s.protocol === 'UDP' && s.port === 53)
  const servesDhcp = listening.some((s) => s.protocol === 'UDP' && s.port === 67)
  const isDhcpClient = device.config.dhcp_client

  return (
    <div className="space-y-4">
      <section>
        <SectionTitle>Network configuration</SectionTitle>

        <label className="mb-2 flex items-center gap-2 rounded-md border border-line bg-panel px-2.5 py-2 text-[11px] text-ink-dim">
          <input
            type="checkbox"
            checked={isDhcpClient}
            onChange={(event) =>
              updateConfig(device.id, { dhcp_client: event.target.checked })
            }
            className="h-3 w-3 accent-[var(--color-accent)]"
          />
          Obtain an address automatically (DHCP)
        </label>

        {isDhcpClient ? (
          <p className="mb-2 text-[10.5px] leading-relaxed text-ink-faint">
            Run <span className="font-mono text-ink-dim">dhcp renew</span> in this
            device&apos;s terminal to request a lease. Whatever the server hands
            back is written into the fields below.
          </p>
        ) : null}

        <div className="space-y-3">
          {device.interfaces.map((iface) => (
            <InterfaceEditor key={iface.id} device={device} iface={iface} />
          ))}

          <div className="space-y-2.5 rounded-md border border-line bg-panel p-3">
            <Field
              label="Default gateway"
              error={gatewayError}
              hint={<span className="text-ink-faint">for other subnets</span>}
            >
              <TextInput
                value={gateway}
                invalid={!!gatewayError}
                placeholder="192.168.1.1"
                spellCheck={false}
                onChange={(event) => setGatewayDraft(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && apply()}
              />
            </Field>

            <Field
              label="DNS server"
              error={dnsError}
              hint={<span className="text-ink-faint">for names</span>}
            >
              <TextInput
                value={dnsServer}
                invalid={!!dnsError}
                placeholder="192.168.1.53"
                spellCheck={false}
                onChange={(event) => setDnsServerDraft(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && apply()}
              />
            </Field>

            <p className="text-[10.5px] leading-relaxed text-ink-faint">
              The gateway carries anything outside this host&apos;s own subnet. The
              DNS server turns names into addresses — without it, only literal
              addresses work.
            </p>

            <Button
              variant={canApply ? 'primary' : 'default'}
              size="sm"
              disabled={!canApply}
              onClick={apply}
              className="w-full"
            >
              {gatewayDirty || dnsDirty ? 'Apply' : 'Applied'}
            </Button>
          </div>
        </div>
      </section>

      <ServicesEditor device={device} />

      {servesDns ? <DnsZoneEditor device={device} /> : null}
      {servesDhcp ? <DhcpPoolEditor device={device} /> : null}

      <VpnEditor device={device} />

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

      {dnsCache.length > 0 ? (
        <section>
          <SectionTitle>Resolved names</SectionTitle>
          <table className="w-full overflow-hidden rounded-md border border-line bg-panel text-[11px]">
            <tbody className="font-mono text-ink-dim">
              {dnsCache.map(([name, ip]) => (
                <tr key={name} className="border-t border-line-soft first:border-t-0">
                  <td className="px-2.5 py-1.5">{name}</td>
                  <td className="px-2.5 py-1.5 text-right">{ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  )
}
