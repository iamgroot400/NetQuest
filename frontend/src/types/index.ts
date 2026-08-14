/**
 * Mirrors the Pydantic schemas in `backend/app/schemas/`.
 * Keep the two in step: the topology document travels over the wire verbatim.
 */

export const TOPOLOGY_VERSION = 1

export type DeviceType = 'pc' | 'switch' | 'router' | 'server' | 'firewall'

export type TransportProtocol = 'TCP' | 'UDP'

export interface Service {
  name: string
  protocol: TransportProtocol
  port: number
  enabled: boolean
}

export type DnsRecordType = 'A' | 'CNAME' | 'MX'

export interface DnsRecord {
  name: string
  type: DnsRecordType
  value: string
  priority: number
}

export interface DhcpPool {
  start: string
  end: string
  netmask: string
  gateway: string | null
  dns: string | null
  lease_seconds: number
  enabled: boolean
}

export type FirewallAction = 'allow' | 'deny'
export type RuleProtocol = 'any' | 'tcp' | 'udp' | 'icmp'

export interface FirewallRule {
  action: FirewallAction
  protocol: RuleProtocol
  port: number | null
  source: string
  destination: string
  description: string
}

export interface NatConfig {
  enabled: boolean
  outside_interface_id: string | null
}

export interface VpnConfig {
  server: string | null
  remote_network: string | null
  remote_netmask: string | null
  tunnel_ip: string | null
  is_gateway: boolean
  enabled: boolean
}

export interface WellKnownService {
  name: string
  protocol: TransportProtocol
  port: number
  description: string
}

export interface Position {
  x: number
  y: number
}

export interface NetworkInterface {
  id: string
  name: string
  mac: string
  ipv4: string | null
  netmask: string | null
  enabled: boolean
}

export interface StaticRoute {
  destination: string
  netmask: string
  gateway: string
}

export interface DeviceConfig {
  gateway: string | null
  dns_server: string | null
  dhcp_client: boolean
  static_routes: StaticRoute[]
  services: Service[]
  dns_records: DnsRecord[]
  dhcp_pool: DhcpPool | null
  firewall_rules: FirewallRule[]
  firewall_default_policy: FirewallAction
  nat: NatConfig | null
  vpn: VpnConfig | null
}

/** Tables the devices learned. Round-tripped between commands, dropped on export. */
export interface DeviceRuntime {
  arp_table: Record<string, string>
  mac_table: Record<string, string>
  dns_cache: Record<string, string>
  dhcp_leases: Record<string, string>
  firewall_hits: Record<string, number>
}

export interface Device {
  id: string
  type: DeviceType
  name: string
  position: Position
  interfaces: NetworkInterface[]
  config: DeviceConfig
  runtime: DeviceRuntime
}

export interface LinkEnd {
  device_id: string
  interface_id: string
}

export type LinkStatus = 'up' | 'down'

export interface Link {
  id: string
  a: LinkEnd
  b: LinkEnd
  status: LinkStatus
}

export interface TopologyDocument {
  version: number
  name: string
  devices: Device[]
  links: Link[]
}

// -- simulation ---------------------------------------------------------

export type EventSeverity = 'info' | 'success' | 'warning' | 'error'

export interface SimEvent {
  seq: number
  type: string
  message: string
  severity: EventSeverity
  device_id: string | null
  device_name: string | null
  interface_id: string | null
  interface_name: string | null
  link_id: string | null
  from_device_id: string | null
  to_device_id: string | null
  frame_uid: string | null
  flow_id: string | null
}

export interface PacketSnapshot {
  frame_uid: string
  flow_id: string
  summary: string
  ethertype: string
  src_mac: string
  dst_mac: string
  protocol: string | null
  src_ip: string | null
  dst_ip: string | null
  ttl: number | null
  length: number | null
  icmp_type: string | null
  icmp_code: string | null
  icmp_sequence: number | null
  icmp_identifier: number | null
  arp_operation: string | null
  arp_sender_ip: string | null
  arp_target_ip: string | null
  arp_sender_mac: string | null
  arp_target_mac: string | null
  transport_protocol: string | null
  src_port: number | null
  dst_port: number | null
  tcp_flag: string | null
  dns_query_name: string | null
  dns_query_type: string | null
  dns_status: string | null
  dns_answers: string[]
  dhcp_type: string | null
  dhcp_offered_ip: string | null
  /** True when this packet carries another IPv4 packet inside a VPN tunnel. */
  encapsulated: boolean
  inner_summary: string | null
  path: string[]
}

export interface RouteEntry {
  destination: string
  netmask: string
  gateway: string | null
  interface_id: string
  kind: string
  prefix_length: number
}

export interface NatTranslation {
  inside_ip: string
  inside_port: number | null
  outside_ip: string
  outside_port: number | null
  protocol: string
  destination_ip: string
}

/** What DHCP configured on a client, written back into the topology document. */
export interface AssignedConfig {
  interface_id: string | null
  ipv4: string | null
  netmask: string | null
  gateway: string | null
  dns_server: string | null
  lease_seconds: number | null
  server_ip: string | null
}

export interface DeviceState {
  arp_table: Record<string, string>
  mac_table: Record<string, string>
  routing_table: RouteEntry[]
  dns_cache: Record<string, string>
  dhcp_leases: Record<string, string>
  firewall_hits: Record<string, number>
  nat_translations: NatTranslation[]
  assigned: AssignedConfig | null
}

export type ConnectionOutcome =
  | 'open'
  | 'refused'
  | 'filtered'
  | 'unreachable'
  | 'no-route'
  | 'dns-failure'
  | 'no-source-address'

export interface ConnectionResult {
  reachable: boolean
  outcome: ConnectionOutcome
  detail: string
  target: string
  resolved_ip: string | null
  port: number | null
  protocol: TransportProtocol
  /** Devices the outbound traffic actually crossed, in order. */
  path: string[]
  blocked_at: string | null
  blocked_reason: string | null
  dns_detail: string | null
  events: SimEvent[]
  packets: PacketSnapshot[]
  device_state: Record<string, DeviceState>
}

export interface CommandResponse {
  output: string[]
  events: SimEvent[]
  packets: PacketSnapshot[]
  device_state: Record<string, DeviceState>
  success: boolean
}

export interface ValidationIssue {
  severity: 'error' | 'warning'
  device_id: string | null
  device_name: string | null
  interface_id: string | null
  message: string
}

export interface ValidationResponse {
  valid: boolean
  issues: ValidationIssue[]
}

export interface CommandReference {
  name: string
  usage: string
  summary: string
}

// -- challenges ---------------------------------------------------------

export type ObjectiveType =
  | 'device_exists'
  | 'link_exists'
  | 'interface_configured'
  | 'in_subnet'
  | 'ping_succeeds'
  | 'ping_fails'
  | 'dns_resolves'
  | 'service_reachable'
  | 'service_blocked'
  | 'service_enabled'
  | 'dhcp_assigns'

export type ChallengeCategory =
  | 'beginner'
  | 'switching'
  | 'routing'
  | 'troubleshooting'
  | 'services'
  | 'security'

export interface Objective {
  type: ObjectiveType
  description: string | null
  device_type: DeviceType | null
  count: number | null
  a: string | null
  b: string | null
  device: string | null
  interface: string | null
  ipv4: string | null
  netmask: string | null
  gateway: string | null
  subnet: string | null
  source: string | null
  destination: string | null
  name: string | null
  expects: string | null
  port: number | null
  protocol: string
}

export interface Challenge {
  id: string
  name: string
  category: ChallengeCategory
  difficulty: number
  xp: number
  level: number
  description: string
  brief: string
  hints: string[]
  /** Shown once solved: what happened, why, and what it teaches. */
  explanation: string
  topology: TopologyDocument | null
  objectives: Objective[]
  requires: string[]
}

export interface ObjectiveResult {
  index: number
  type: ObjectiveType
  description: string
  complete: boolean
  detail: string
}

export interface ChallengeValidationResponse {
  challenge_id: string
  complete: boolean
  objectives: ObjectiveResult[]
  xp: number
}
