/**
 * Device creation and naming.
 *
 * Default names (PC-01, Switch-01, …) are part of the contract with the
 * challenge files, which refer to devices by name.
 */

import type { Device, DeviceType, Link, NetworkInterface, Position } from '@/types'

interface DeviceProfile {
  label: string
  /** Prefix used for auto-naming; challenge objectives rely on these. */
  prefix: string
  ports: number
  /** Layer 3 devices get address fields in the config panel. */
  addressable: boolean
  blurb: string
}

export const DEVICE_PROFILES: Record<DeviceType, DeviceProfile> = {
  pc: {
    label: 'PC',
    prefix: 'PC',
    ports: 1,
    addressable: true,
    blurb: 'An end host with one network adapter.',
  },
  switch: {
    label: 'Switch',
    prefix: 'Switch',
    ports: 8,
    addressable: false,
    blurb: 'Layer 2. Learns MAC addresses and forwards frames.',
  },
  router: {
    label: 'Router',
    prefix: 'Router',
    ports: 2,
    addressable: true,
    blurb: 'Layer 3. Joins two subnets and forwards IPv4.',
  },
  server: {
    label: 'Server',
    prefix: 'Server',
    ports: 1,
    addressable: true,
    blurb: 'An end host that answers requests.',
  },
}

export const DEVICE_ORDER: DeviceType[] = ['pc', 'switch', 'router', 'server']

let sequence = Date.now() % 100000

function uid(prefix: string): string {
  sequence += 1
  return `${prefix}-${sequence.toString(36)}`
}

/**
 * Locally administered MAC, matching the backend's generator format.
 * Uniqueness comes from a counter rather than the device index, because
 * devices can be deleted and re-added in any order.
 */
function generateMac(): string {
  sequence += 1
  const value = sequence & 0xffffff
  const bytes = [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
  return ['02', '00', '5E', ...bytes.map((b) => b.toString(16).padStart(2, '0'))]
    .join(':')
    .toUpperCase()
}

export function nextDeviceName(type: DeviceType, existing: Device[]): string {
  const { prefix } = DEVICE_PROFILES[type]
  const taken = new Set(existing.map((d) => d.name.toLowerCase()))
  for (let n = 1; n < 1000; n += 1) {
    const candidate = `${prefix}-${String(n).padStart(2, '0')}`
    if (!taken.has(candidate.toLowerCase())) return candidate
  }
  return `${prefix}-${uid('x')}`
}

export function createDevice(
  type: DeviceType,
  position: Position,
  existing: Device[],
): Device {
  const profile = DEVICE_PROFILES[type]
  const id = uid('dev')
  return {
    id,
    type,
    name: nextDeviceName(type, existing),
    position,
    interfaces: Array.from({ length: profile.ports }, (_, index) => ({
      id: `${id}-eth${index}`,
      name: `eth${index}`,
      mac: generateMac(),
      ipv4: null,
      netmask: profile.addressable ? '255.255.255.0' : null,
      enabled: true,
    })),
    config: { gateway: null, static_routes: [] },
    runtime: { arp_table: {}, mac_table: {} },
  }
}

export function createLink(
  a: { deviceId: string; interfaceId: string },
  b: { deviceId: string; interfaceId: string },
): Link {
  return {
    id: uid('lnk'),
    a: { device_id: a.deviceId, interface_id: a.interfaceId },
    b: { device_id: b.deviceId, interface_id: b.interfaceId },
    status: 'up',
  }
}

/** The first interface with no cable attached, or null when the device is full. */
export function firstFreeInterface(
  device: Device,
  links: Link[],
): NetworkInterface | null {
  const used = new Set(links.flatMap((l) => [l.a.interface_id, l.b.interface_id]))
  return device.interfaces.find((i) => !used.has(i.id)) ?? null
}

export function interfaceOf(device: Device, interfaceId: string): NetworkInterface | null {
  return device.interfaces.find((i) => i.id === interfaceId) ?? null
}

/** Which of a link's two ends belongs to this device. */
export function endFor(link: Link, deviceId: string) {
  if (link.a.device_id === deviceId) return link.a
  if (link.b.device_id === deviceId) return link.b
  return null
}
