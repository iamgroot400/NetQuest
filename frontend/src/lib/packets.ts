/** How packets are coloured and described, consistently across every surface. */

import type { PacketSnapshot } from '@/types'

export type PacketTone = 'arp' | 'request' | 'reply' | 'error' | 'other'

export function packetTone(packet: PacketSnapshot | null | undefined): PacketTone {
  if (!packet) return 'other'
  if (packet.ethertype === 'ARP') return 'arp'
  switch (packet.icmp_type) {
    case 'echo-request':
      return 'request'
    case 'echo-reply':
      return 'reply'
    case 'destination-unreachable':
    case 'time-exceeded':
      return 'error'
    default:
      return 'other'
  }
}

export const TONE_HEX: Record<PacketTone, string> = {
  arp: '#a78bfa',
  request: '#22d3ee',
  reply: '#34d399',
  error: '#f87171',
  other: '#9aa7b8',
}

export const TONE_CLASS: Record<PacketTone, string> = {
  arp: 'text-switch',
  request: 'text-accent',
  reply: 'text-ok',
  error: 'text-bad',
  other: 'text-ink-dim',
}

export function packetLabel(packet: PacketSnapshot): string {
  if (packet.ethertype === 'ARP') {
    return packet.arp_operation === 'request' ? 'ARP Request' : 'ARP Reply'
  }
  if (packet.icmp_type) return `ICMP ${packet.icmp_type}`
  return packet.protocol ?? packet.ethertype
}

/** Severity styling for the event log, keyed by the backend's severity field. */
export const SEVERITY_CLASS: Record<string, string> = {
  info: 'text-ink-dim',
  success: 'text-ok',
  warning: 'text-warn',
  error: 'text-bad',
}
