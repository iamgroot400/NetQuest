/**
 * One place that decides what each kind of device looks like.
 *
 * Keyed by *role* rather than type, so a plain server that gains a DNS zone
 * starts showing a DNS icon without changing what it is.
 */

import {
  Book,
  Globe,
  Lock,
  Monitor,
  Network,
  Router,
  Server,
  Shield,
  Ticket,
  type LucideIcon,
} from 'lucide-react'

import type { Device } from '@/types'

import { deviceRole } from './devices'

export interface DeviceVisual {
  icon: LucideIcon
  /** Tailwind classes for the icon chip and the activity ring. */
  text: string
  chip: string
  ring: string
  /** Flat colour for the minimap, which cannot use CSS classes. */
  hex: string
}

const PC: DeviceVisual = {
  icon: Monitor,
  text: 'text-pc',
  chip: 'bg-pc/10',
  ring: 'ring-pc/60',
  hex: '#60a5fa',
}
const SWITCH: DeviceVisual = {
  icon: Network,
  text: 'text-switch',
  chip: 'bg-switch/10',
  ring: 'ring-switch/60',
  hex: '#a78bfa',
}
const ROUTER: DeviceVisual = {
  icon: Router,
  text: 'text-router',
  chip: 'bg-router/10',
  ring: 'ring-router/60',
  hex: '#fbbf24',
}
const FIREWALL: DeviceVisual = {
  icon: Shield,
  text: 'text-firewall',
  chip: 'bg-firewall/10',
  ring: 'ring-firewall/60',
  hex: '#fb923c',
}
const SERVER: DeviceVisual = {
  icon: Server,
  text: 'text-server',
  chip: 'bg-server/10',
  ring: 'ring-server/60',
  hex: '#34d399',
}

export const VISUALS: Record<string, DeviceVisual> = {
  pc: PC,
  switch: SWITCH,
  router: ROUTER,
  firewall: FIREWALL,
  server: SERVER,
  'web-server': { ...SERVER, icon: Globe },
  'dns-server': { ...SERVER, icon: Book },
  'dhcp-server': { ...SERVER, icon: Ticket },
  'vpn-server': { ...SERVER, icon: Lock },
}

export function visualForRole(role: string): DeviceVisual {
  return VISUALS[role] ?? SERVER
}

export function visualFor(device: Device): DeviceVisual {
  return visualForRole(deviceRole(device))
}

/** A short line under the device name on the canvas. */
export function deviceSubtitle(device: Device): string {
  if (device.type === 'switch') return `${device.interfaces.length} ports`
  if (device.type === 'firewall') {
    const count = device.config.firewall_rules.length
    return count === 0
      ? `no rules · ${device.config.firewall_default_policy}`
      : `${count} rule${count === 1 ? '' : 's'} · ${device.config.firewall_default_policy}`
  }
  const addressed = device.interfaces.find((i) => i.ipv4)
  if (addressed?.ipv4) return addressed.ipv4
  return device.config.dhcp_client ? 'awaiting DHCP' : 'no address'
}
