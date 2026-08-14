/** How packets are coloured and described, consistently across every surface. */

import type { PacketSnapshot } from '@/types'

export type PacketTone =
  | 'arp'
  | 'request'
  | 'reply'
  | 'error'
  | 'dns'
  | 'dhcp'
  | 'tunnel'
  | 'other'

export function packetTone(packet: PacketSnapshot | null | undefined): PacketTone {
  if (!packet) return 'other'
  if (packet.ethertype === 'ARP') return 'arp'
  if (packet.encapsulated) return 'tunnel'
  if (packet.dhcp_type) return 'dhcp'
  if (packet.dns_query_name) {
    return packet.dns_status && packet.dns_status !== 'NOERROR' ? 'error' : 'dns'
  }
  if (packet.tcp_flag === 'RST') return 'error'
  if (packet.tcp_flag === 'SYN-ACK') return 'reply'
  if (packet.tcp_flag === 'SYN') return 'request'
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
  dns: '#818cf8',
  dhcp: '#fbbf24',
  tunnel: '#f472b6',
  other: '#9aa7b8',
}

export const TONE_CLASS: Record<PacketTone, string> = {
  arp: 'text-switch',
  request: 'text-accent',
  reply: 'text-ok',
  error: 'text-bad',
  dns: 'text-indigo-400',
  dhcp: 'text-router',
  tunnel: 'text-pink-400',
  other: 'text-ink-dim',
}

export function packetLabel(packet: PacketSnapshot): string {
  if (packet.ethertype === 'ARP') {
    return packet.arp_operation === 'request' ? 'ARP Request' : 'ARP Reply'
  }
  if (packet.encapsulated) return 'VPN tunnel'
  if (packet.dhcp_type) return `DHCP ${packet.dhcp_type}`
  if (packet.dns_query_name) {
    return packet.dns_status ? `DNS ${packet.dns_status}` : 'DNS query'
  }
  if (packet.icmp_type) return `ICMP ${packet.icmp_type}`
  if (packet.tcp_flag) return `TCP ${packet.tcp_flag}`
  if (packet.transport_protocol) return `${packet.transport_protocol} datagram`
  return packet.protocol ?? packet.ethertype
}

/** Severity styling for the event log, keyed by the backend's severity field. */
export const SEVERITY_CLASS: Record<string, string> = {
  info: 'text-ink-dim',
  success: 'text-ok',
  warning: 'text-warn',
  error: 'text-bad',
}
