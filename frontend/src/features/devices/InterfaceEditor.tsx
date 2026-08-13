import { Cable, Check, Unplug } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field, TextInput } from '@/components/ui/Field'
import { COMMON_MASKS, isValidIpv4, isValidNetmask, netmaskToPrefix } from '@/lib/net'
import { useTopologyStore } from '@/stores/topologyStore'
import type { Device, NetworkInterface } from '@/types'

interface Props {
  device: Device
  iface: NetworkInterface
}

/** Address form for one interface. Changes only reach the simulation on Apply. */
export function InterfaceEditor({ device, iface }: Props) {
  const updateInterface = useTopologyStore((state) => state.updateInterface)
  const links = useTopologyStore((state) => state.links)
  const devices = useTopologyStore((state) => state.devices)

  const [ipv4, setIpv4] = useState(iface.ipv4 ?? '')
  const [netmask, setNetmask] = useState(iface.netmask ?? '')

  // Re-sync when the panel switches to a different interface, or when the
  // topology is replaced by loading a file or starting a mission.
  useEffect(() => {
    setIpv4(iface.ipv4 ?? '')
    setNetmask(iface.netmask ?? '')
  }, [iface.id, iface.ipv4, iface.netmask])

  const ipError = ipv4 !== '' && !isValidIpv4(ipv4) ? 'Not a valid IPv4 address.' : null
  const maskError =
    netmask !== '' && !isValidNetmask(netmask)
      ? 'A mask must be a solid run of ones, e.g. 255.255.255.0.'
      : null

  const dirty = (iface.ipv4 ?? '') !== ipv4 || (iface.netmask ?? '') !== netmask
  const canApply = dirty && !ipError && !maskError

  const apply = () => {
    if (!canApply) return
    updateInterface(device.id, iface.id, {
      ipv4: ipv4.trim() || null,
      netmask: netmask.trim() || null,
    })
  }

  const link = links.find(
    (l) => l.a.interface_id === iface.id || l.b.interface_id === iface.id,
  )
  const peer = (() => {
    if (!link) return null
    const far = link.a.interface_id === iface.id ? link.b : link.a
    const farDevice = devices.find((d) => d.id === far.device_id)
    const farIface = farDevice?.interfaces.find((i) => i.id === far.interface_id)
    return farDevice && farIface ? `${farDevice.name} ${farIface.name}` : null
  })()

  const prefix = isValidNetmask(netmask) ? netmaskToPrefix(netmask) : null

  return (
    <div className="rounded-md border border-line bg-panel p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-[13px] font-semibold text-ink">
            {iface.name}
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
              iface.enabled ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad'
            }`}
          >
            {iface.enabled ? 'UP' : 'DOWN'}
          </span>
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => updateInterface(device.id, iface.id, { enabled: !iface.enabled })}
        >
          {iface.enabled ? 'Shut down' : 'Bring up'}
        </Button>
      </div>

      <div className="space-y-2.5">
        <Field label="IPv4 address" error={ipError}>
          <TextInput
            value={ipv4}
            invalid={!!ipError}
            placeholder="192.168.1.10"
            spellCheck={false}
            onChange={(event) => setIpv4(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && apply()}
          />
        </Field>

        <Field
          label="Subnet mask"
          error={maskError}
          hint={prefix !== null ? `/${prefix}` : undefined}
        >
          <TextInput
            value={netmask}
            invalid={!!maskError}
            placeholder="255.255.255.0"
            spellCheck={false}
            list={`masks-${iface.id}`}
            onChange={(event) => setNetmask(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && apply()}
          />
          <datalist id={`masks-${iface.id}`}>
            {COMMON_MASKS.map((mask) => (
              <option key={mask} value={mask} />
            ))}
          </datalist>
        </Field>

        <Button
          variant={canApply ? 'primary' : 'default'}
          size="sm"
          disabled={!canApply}
          onClick={apply}
          className="w-full"
        >
          <Check size={13} />
          {dirty ? 'Apply' : 'Applied'}
        </Button>
      </div>

      <dl className="mt-3 space-y-1 border-t border-line-soft pt-2.5 text-[11px]">
        <div className="flex justify-between gap-2">
          <dt className="text-ink-faint">MAC address</dt>
          <dd className="font-mono text-ink-dim">{iface.mac}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-ink-faint">Cable</dt>
          <dd className="flex items-center gap-1 truncate">
            {peer ? (
              <>
                <Cable size={11} className={link?.status === 'up' ? 'text-ok' : 'text-bad'} />
                <span className="truncate text-ink-dim">{peer}</span>
              </>
            ) : (
              <>
                <Unplug size={11} className="text-ink-faint" />
                <span className="text-ink-faint">not connected</span>
              </>
            )}
          </dd>
        </div>
      </dl>
    </div>
  )
}
