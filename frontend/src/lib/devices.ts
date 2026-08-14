/**
 * Device creation and naming.
 *
 * The palette offers *presets* rather than raw device types: a DNS server and
 * a web server are both `server`, they just start with different services
 * enabled. Default names (PC-01, WEB-01, …) are part of the contract with the
 * challenge files, which refer to devices by name.
 */

import type {
  Device,
  DeviceConfig,
  DeviceType,
  DnsRecord,
  Link,
  NetworkInterface,
  Position,
  Service,
} from '@/types'

export interface DevicePreset {
  /** Palette key, and what `addDevice` is called with. */
  id: string
  type: DeviceType
  label: string
  /** Auto-naming prefix; challenge objectives rely on these. */
  prefix: string
  ports: number
  /** Layer 3 devices get address fields in the config panel. */
  addressable: boolean
  blurb: string
  services?: Service[]
  dnsRecords?: DnsRecord[]
  /** Marks the preset in the palette as a distinct role. */
  role: 'endpoint' | 'infrastructure' | 'service'
}

function tcp(name: string, port: number): Service {
  return { name, protocol: 'TCP', port, enabled: true }
}

function udp(name: string, port: number): Service {
  return { name, protocol: 'UDP', port, enabled: true }
}

export const DEVICE_PRESETS: DevicePreset[] = [
  {
    id: 'pc',
    type: 'pc',
    label: 'PC',
    prefix: 'PC',
    ports: 1,
    addressable: true,
    role: 'endpoint',
    blurb: 'An end host with one network adapter.',
  },
  {
    id: 'switch',
    type: 'switch',
    label: 'Switch',
    prefix: 'Switch',
    ports: 8,
    addressable: false,
    role: 'infrastructure',
    blurb: 'Layer 2. Learns MAC addresses and forwards frames.',
  },
  {
    id: 'router',
    type: 'router',
    label: 'Router',
    prefix: 'Router',
    ports: 2,
    addressable: true,
    role: 'infrastructure',
    blurb: 'Layer 3. Joins subnets, forwards IPv4, and can do NAT.',
  },
  {
    id: 'firewall',
    type: 'firewall',
    label: 'Firewall',
    prefix: 'Firewall',
    ports: 2,
    addressable: false,
    role: 'infrastructure',
    blurb: 'Sits inline and filters traffic by protocol, port and address.',
  },
  {
    id: 'web-server',
    type: 'server',
    label: 'Web Server',
    prefix: 'WEB',
    ports: 1,
    addressable: true,
    role: 'service',
    blurb: 'A server listening on HTTP and HTTPS.',
    services: [tcp('HTTP', 80), tcp('HTTPS', 443)],
  },
  {
    id: 'dns-server',
    type: 'server',
    label: 'DNS Server',
    prefix: 'DNS',
    ports: 1,
    addressable: true,
    role: 'service',
    blurb: 'Resolves names to addresses from a zone you edit.',
    services: [udp('DNS', 53)],
    dnsRecords: [],
  },
  {
    id: 'dhcp-server',
    type: 'server',
    label: 'DHCP Server',
    prefix: 'DHCP',
    ports: 1,
    addressable: true,
    role: 'service',
    blurb: 'Hands addresses, gateway and DNS to clients that ask.',
    services: [udp('DHCP', 67)],
  },
  {
    id: 'server',
    type: 'server',
    label: 'Server',
    prefix: 'Server',
    ports: 1,
    addressable: true,
    role: 'service',
    blurb: 'A bare server. Add whichever services you need.',
  },
]

export const PRESETS_BY_ID: Record<string, DevicePreset> = Object.fromEntries(
  DEVICE_PRESETS.map((preset) => [preset.id, preset]),
)

/** Fallback used when only a device type is known (loading a saved file). */
export const PRESET_BY_TYPE: Record<DeviceType, DevicePreset> = {
  pc: PRESETS_BY_ID.pc!,
  switch: PRESETS_BY_ID.switch!,
  router: PRESETS_BY_ID.router!,
  firewall: PRESETS_BY_ID.firewall!,
  server: PRESETS_BY_ID.server!,
}

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

export function emptyConfig(): DeviceConfig {
  return {
    gateway: null,
    dns_server: null,
    dhcp_client: false,
    static_routes: [],
    services: [],
    dns_records: [],
    dhcp_pool: null,
    firewall_rules: [],
    firewall_default_policy: 'allow',
    nat: null,
    vpn: null,
  }
}

export function nextDeviceName(prefix: string, existing: Device[]): string {
  const taken = new Set(existing.map((d) => d.name.toLowerCase()))
  for (let n = 1; n < 1000; n += 1) {
    const candidate = `${prefix}-${String(n).padStart(2, '0')}`
    if (!taken.has(candidate.toLowerCase())) return candidate
  }
  return `${prefix}-${uid('x')}`
}

export function createDevice(
  presetId: string,
  position: Position,
  existing: Device[],
): Device {
  const preset = PRESETS_BY_ID[presetId] ?? PRESETS_BY_ID.pc!
  const id = uid('dev')

  const config = emptyConfig()
  if (preset.services) config.services = preset.services.map((s) => ({ ...s }))
  if (preset.dnsRecords) config.dns_records = preset.dnsRecords.map((r) => ({ ...r }))
  if (preset.id === 'dhcp-server') {
    // A pool the learner can see and edit immediately, rather than an empty
    // form that silently serves nobody.
    config.dhcp_pool = {
      start: '192.168.1.100',
      end: '192.168.1.150',
      netmask: '255.255.255.0',
      gateway: null,
      dns: null,
      lease_seconds: 86400,
      enabled: true,
    }
  }

  return {
    id,
    type: preset.type,
    name: nextDeviceName(preset.prefix, existing),
    position,
    interfaces: Array.from({ length: preset.ports }, (_, index) => ({
      id: `${id}-eth${index}`,
      name: `eth${index}`,
      mac: generateMac(),
      ipv4: null,
      netmask: preset.addressable ? '255.255.255.0' : null,
      enabled: true,
    })),
    config,
    runtime: {
      arp_table: {},
      mac_table: {},
      dns_cache: {},
      dhcp_leases: {},
      firewall_hits: {},
    },
  }
}

/**
 * What a device is *acting* as, from its configuration.
 * Drives the icon, so a plain server that gains a DNS zone starts looking
 * like a DNS server without changing its type.
 */
export function deviceRole(device: Device): string {
  if (device.type !== 'server') return device.type
  const ports = device.config.services.filter((s) => s.enabled).map((s) => s.port)
  if (device.config.dhcp_pool && ports.includes(67)) return 'dhcp-server'
  if (ports.includes(53)) return 'dns-server'
  if (device.config.vpn?.is_gateway) return 'vpn-server'
  if (ports.includes(80) || ports.includes(443)) return 'web-server'
  return 'server'
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
