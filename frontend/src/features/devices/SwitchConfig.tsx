import { Cable, Unplug } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { SectionTitle } from '@/components/ui/Field'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device } from '@/types'

export function SwitchConfig({ device }: { device: Device }) {
  const links = useTopologyStore((state) => state.links)
  const devices = useTopologyStore((state) => state.devices)
  const updateInterface = useTopologyStore((state) => state.updateInterface)

  const macEntries = Object.entries(device.runtime.mac_table)
  const portName = (interfaceId: string) =>
    device.interfaces.find((i) => i.id === interfaceId)?.name ?? '?'

  return (
    <div className="space-y-4">
      <p className="rounded-md border border-line bg-panel px-3 py-2.5 text-[11px] leading-relaxed text-ink-dim">
        A switch needs no addresses. It works purely at Layer 2: it learns which
        MAC address lives on which port and forwards frames accordingly.
      </p>

      <section>
        <SectionTitle>Ports</SectionTitle>
        <div className="overflow-hidden rounded-md border border-line bg-panel">
          {device.interfaces.map((iface, index) => {
            const link = links.find(
              (l) => l.a.interface_id === iface.id || l.b.interface_id === iface.id,
            )
            const peer = (() => {
              if (!link) return null
              const far = link.a.interface_id === iface.id ? link.b : link.a
              const farDevice = devices.find((d) => d.id === far.device_id)
              return farDevice?.name ?? null
            })()

            return (
              <div
                key={iface.id}
                className={`flex items-center gap-2 px-2.5 py-1.5 text-[11px] ${
                  index > 0 ? 'border-t border-line-soft' : ''
                }`}
              >
                <span className="w-12 shrink-0 font-mono text-ink-dim">{iface.name}</span>
                <span className="flex min-w-0 flex-1 items-center gap-1.5">
                  {peer ? (
                    <>
                      <Cable
                        size={11}
                        className={link?.status === 'up' ? 'text-ok' : 'text-bad'}
                      />
                      <span className="truncate text-ink-dim">{peer}</span>
                    </>
                  ) : (
                    <>
                      <Unplug size={11} className="text-ink-faint" />
                      <span className="text-ink-faint">free</span>
                    </>
                  )}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    updateInterface(device.id, iface.id, { enabled: !iface.enabled })
                  }
                >
                  {iface.enabled ? 'Shut' : 'Enable'}
                </Button>
              </div>
            )
          })}
        </div>
      </section>

      <section>
        <SectionTitle>MAC address table</SectionTitle>
        {macEntries.length === 0 ? (
          <p className="rounded-md border border-line bg-panel px-3 py-3 text-[11px] leading-relaxed text-ink-faint">
            Empty. The table fills as frames arrive — until then the switch floods
            everything it does not recognise.
          </p>
        ) : (
          <table className="w-full overflow-hidden rounded-md border border-line bg-panel text-[11px]">
            <thead>
              <tr className="border-b border-line text-left text-ink-faint">
                <th className="px-2.5 py-1.5 font-medium">MAC address</th>
                <th className="px-2.5 py-1.5 font-medium">Port</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-dim">
              {macEntries.map(([mac, interfaceId]) => (
                <tr key={mac} className="border-t border-line-soft">
                  <td className="px-2.5 py-1.5">{mac}</td>
                  <td className="px-2.5 py-1.5">{portName(interfaceId)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
