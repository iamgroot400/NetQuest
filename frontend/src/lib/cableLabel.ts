import type { Device, Link, LinkEnd } from '@/types'

export interface CableEndpoint {
  device: Device | null
  interfaceName: string
}

function endpointOf(end: LinkEnd, devices: Device[]): CableEndpoint {
  const device = devices.find((d) => d.id === end.device_id) ?? null
  const interfaceName = device?.interfaces.find((i) => i.id === end.interface_id)?.name ?? '?'
  return { device, interfaceName }
}

/** The two named ends of a cable, in a consistent `Device eth0` form. */
export function cableEndpoints(link: Link, devices: Device[]) {
  return {
    a: endpointOf(link.a, devices),
    b: endpointOf(link.b, devices),
  }
}

function formatEndpoint({ device, interfaceName }: CableEndpoint): string {
  return `${device?.name ?? 'unknown'} ${interfaceName}`
}

/** Short label for the canvas — just the ports, since the devices are visible either side. */
export function shortCableLabel(link: Link, devices: Device[]): string {
  const { a, b } = cableEndpoints(link, devices)
  return `${a.interfaceName} ↔ ${b.interfaceName}`
}

/** Full label for panels — `PC-01 eth0 ↔ Switch-01 eth2`. */
export function fullCableLabel(link: Link, devices: Device[]): string {
  const { a, b } = cableEndpoints(link, devices)
  return `${formatEndpoint(a)} ↔ ${formatEndpoint(b)}`
}
