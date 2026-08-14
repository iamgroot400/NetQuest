/** Mirrors `backend/app/simulation/transport/services.py`. */

import type { Service, TransportProtocol, WellKnownService } from '@/types'

export const WELL_KNOWN: WellKnownService[] = [
  { name: 'HTTP', protocol: 'TCP', port: 80, description: 'Unencrypted web traffic' },
  { name: 'HTTPS', protocol: 'TCP', port: 443, description: 'Encrypted web traffic' },
  { name: 'DNS', protocol: 'UDP', port: 53, description: 'Resolves names to addresses' },
  { name: 'DHCP', protocol: 'UDP', port: 67, description: 'Hands out addresses to clients' },
  { name: 'SSH', protocol: 'TCP', port: 22, description: 'Remote shell' },
  { name: 'FTP', protocol: 'TCP', port: 21, description: 'File transfer' },
  { name: 'SMTP', protocol: 'TCP', port: 25, description: 'Mail delivery' },
  { name: 'VPN', protocol: 'UDP', port: 1194, description: 'Tunnel endpoint' },
]

export function serviceKey(protocol: TransportProtocol, port: number): string {
  return `${protocol}:${port}`
}

export function describePort(protocol: TransportProtocol, port: number): string {
  const known = WELL_KNOWN.find((s) => s.protocol === protocol && s.port === port)
  return `${port}/${protocol.toLowerCase()}${known ? ` (${known.name})` : ''}`
}

export function findService(
  services: Service[],
  protocol: TransportProtocol,
  port: number,
): Service | undefined {
  return services.find((s) => s.protocol === protocol && s.port === port)
}
