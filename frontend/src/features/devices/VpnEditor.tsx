import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, SectionTitle, TextInput } from '@/components/ui/Field'
import { isValidIpv4, isValidNetmask } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, VpnConfig } from '@/types'

const BLANK: VpnConfig = {
  server: null,
  remote_network: null,
  remote_netmask: '255.255.255.0',
  tunnel_ip: null,
  is_gateway: false,
  enabled: true,
}

/**
 * Tunnel settings. A client wraps traffic for the remote network inside UDP to
 * the gateway; a gateway unwraps it and forwards what was inside.
 */
export function VpnEditor({ device }: { device: Device }) {
  const updateConfig = useTopologyStore((state) => state.updateConfig)
  const vpn = device.config.vpn
  const [draft, setDraft] = useState<VpnConfig>(vpn ?? BLANK)

  useEffect(() => {
    if (vpn) setDraft(vpn)
  }, [vpn])

  if (!vpn) {
    return (
      <section>
        <SectionTitle>VPN</SectionTitle>
        <p className="mb-2 rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
          Not configured. A tunnel lets traffic cross a network that would
          otherwise filter it — the firewall in between sees only the outer UDP
          datagram, never what it carries.
        </p>
        <div className="flex gap-1.5">
          <Button
            size="sm"
            className="flex-1"
            onClick={() => updateConfig(device.id, { vpn: { ...BLANK } })}
          >
            Set up as client
          </Button>
          <Button
            size="sm"
            className="flex-1"
            onClick={() =>
              updateConfig(device.id, { vpn: { ...BLANK, is_gateway: true } })
            }
          >
            Set up as gateway
          </Button>
        </div>
      </section>
    )
  }

  const errors = {
    server:
      !draft.is_gateway && draft.server && !isValidIpv4(draft.server)
        ? 'Not a valid address.'
        : null,
    remote_network:
      !draft.is_gateway && draft.remote_network && !isValidIpv4(draft.remote_network)
        ? 'Not a valid address.'
        : null,
    remote_netmask:
      !draft.is_gateway && draft.remote_netmask && !isValidNetmask(draft.remote_netmask)
        ? 'Not a valid mask.'
        : null,
    tunnel_ip:
      !draft.is_gateway && draft.tunnel_ip && !isValidIpv4(draft.tunnel_ip)
        ? 'Not a valid address.'
        : null,
  }
  const valid = Object.values(errors).every((e) => e === null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(vpn)

  const apply = () => {
    if (!valid || !dirty) return
    updateConfig(device.id, {
      vpn: {
        ...draft,
        server: draft.server?.trim() || null,
        remote_network: draft.remote_network?.trim() || null,
        remote_netmask: draft.remote_netmask?.trim() || null,
        tunnel_ip: draft.tunnel_ip?.trim() || null,
      },
    })
  }

  const listeningOnVpnPort = device.config.services.some(
    (s) => s.enabled && s.protocol === 'UDP' && s.port === 1194,
  )

  return (
    <section>
      <SectionTitle>VPN</SectionTitle>
      <div className="space-y-2.5 rounded-md border border-line bg-panel p-3">
        <label className="flex items-center gap-2 text-[11px] text-ink-dim">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
            className="h-3 w-3 accent-[var(--color-accent)]"
          />
          Tunnel enabled
        </label>
        <label className="flex items-center gap-2 text-[11px] text-ink-dim">
          <input
            type="checkbox"
            checked={draft.is_gateway}
            onChange={(event) =>
              setDraft({ ...draft, is_gateway: event.target.checked })
            }
            className="h-3 w-3 accent-[var(--color-accent)]"
          />
          This device is the gateway
        </label>

        {draft.is_gateway ? (
          <p className="text-[10.5px] leading-relaxed text-ink-faint">
            {listeningOnVpnPort
              ? 'Accepting tunnels on 1194/udp. Traffic that arrives wrapped is unwrapped and forwarded onto this network.'
              : 'Enable the VPN service above (1194/udp) or nothing will be accepted.'}
          </p>
        ) : (
          <>
            <Field label="Gateway address" error={errors.server}>
              <TextInput
                value={draft.server ?? ''}
                invalid={!!errors.server}
                placeholder="10.8.0.10"
                spellCheck={false}
                onChange={(event) => setDraft({ ...draft, server: event.target.value })}
              />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Remote network" error={errors.remote_network}>
                <TextInput
                  value={draft.remote_network ?? ''}
                  invalid={!!errors.remote_network}
                  placeholder="10.8.0.0"
                  spellCheck={false}
                  onChange={(event) =>
                    setDraft({ ...draft, remote_network: event.target.value })
                  }
                />
              </Field>
              <Field label="Mask" error={errors.remote_netmask}>
                <TextInput
                  value={draft.remote_netmask ?? ''}
                  invalid={!!errors.remote_netmask}
                  spellCheck={false}
                  onChange={(event) =>
                    setDraft({ ...draft, remote_netmask: event.target.value })
                  }
                />
              </Field>
            </div>
            <Field
              label="Address inside the tunnel"
              error={errors.tunnel_ip}
              hint={<span className="text-ink-faint">recommended</span>}
            >
              <TextInput
                value={draft.tunnel_ip ?? ''}
                invalid={!!errors.tunnel_ip}
                placeholder="10.8.0.200"
                spellCheck={false}
                onChange={(event) =>
                  setDraft({ ...draft, tunnel_ip: event.target.value })
                }
                onKeyDown={(event) => event.key === 'Enter' && apply()}
              />
            </Field>
            <p className="text-[10.5px] leading-relaxed text-ink-faint">
              Give this an address on the remote network. The gateway answers ARP
              for it, which is what brings replies back through the tunnel instead
              of routing around it.
            </p>
          </>
        )}

        <div className="flex gap-1.5">
          <Button
            variant={valid && dirty ? 'primary' : 'default'}
            size="sm"
            disabled={!valid || !dirty}
            onClick={apply}
            className="flex-1"
          >
            {dirty ? 'Apply' : 'Applied'}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => updateConfig(device.id, { vpn: null })}
          >
            Remove
          </Button>
        </div>
      </div>
    </section>
  )
}
