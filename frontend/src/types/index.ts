/**
 * Mirrors the Pydantic schemas in `backend/app/schemas/`.
 * Keep the two in step: the topology document travels over the wire verbatim.
 */

export const TOPOLOGY_VERSION = 1

export type DeviceType = 'pc' | 'switch' | 'router' | 'server'

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
  static_routes: StaticRoute[]
}

/** Tables the devices learned. Round-tripped between commands, dropped on export. */
export interface DeviceRuntime {
  arp_table: Record<string, string>
  mac_table: Record<string, string>
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

export interface DeviceState {
  arp_table: Record<string, string>
  mac_table: Record<string, string>
  routing_table: RouteEntry[]
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

export type ChallengeCategory = 'beginner' | 'switching' | 'routing' | 'troubleshooting'

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
