/**
 * The topology document — the single source of truth for the whole app.
 *
 * The backend keeps no state: this document is posted with every command and
 * the learned tables that come back are written straight into it.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import { createDevice, createLink, emptyConfig, freeInterfaceOrGrow } from '@/lib/devices'
import type {
  Device,
  DeviceConfig,
  DeviceState,
  Link,
  LinkStatus,
  NetworkInterface,
  Position,
  StaticRoute,
  TopologyDocument,
} from '@/types'
import { TOPOLOGY_VERSION } from '@/types'

export type ConnectResult =
  | { ok: true; link: Link }
  | { ok: false; reason: string }

interface TopologyState {
  name: string
  devices: Device[]
  links: Link[]
  selectedDeviceId: string | null
  selectedLinkId: string | null

  addDevice: (presetId: string, position: Position) => Device
  removeDevice: (deviceId: string) => void
  renameDevice: (deviceId: string, name: string) => void
  moveDevice: (deviceId: string, position: Position) => void
  updateInterface: (
    deviceId: string,
    interfaceId: string,
    patch: Partial<NetworkInterface>,
  ) => void
  setGateway: (deviceId: string, gateway: string | null) => void
  setStaticRoutes: (deviceId: string, routes: StaticRoute[]) => void
  /** Patch any part of a device's configuration — services, DNS, rules, NAT, VPN. */
  updateConfig: (deviceId: string, patch: Partial<DeviceConfig>) => void

  connect: (sourceDeviceId: string, targetDeviceId: string) => ConnectResult
  removeLink: (linkId: string) => void
  setLinkStatus: (linkId: string, status: LinkStatus) => void

  select: (deviceId: string | null, linkId?: string | null) => void

  applyDeviceState: (state: Record<string, DeviceState>) => void
  clearLearnedTables: () => void

  loadDocument: (document: TopologyDocument) => void
  reset: () => void
  rename: (name: string) => void
}

const EMPTY_NAME = 'Untitled network'

function patchDevice(devices: Device[], deviceId: string, fn: (device: Device) => Device) {
  return devices.map((device) => (device.id === deviceId ? fn(device) : device))
}

function emptyRuntime() {
  return {
    arp_table: {},
    mac_table: {},
    dns_cache: {},
    dhcp_leases: {},
    firewall_hits: {},
  }
}

/** Fill in anything a document is missing, so older saved files keep working. */
export function normalizeDevice(device: Device): Device {
  return {
    ...device,
    config: { ...emptyConfig(), ...(device.config ?? {}) },
    runtime: { ...emptyRuntime(), ...(device.runtime ?? {}) },
  }
}

export const useTopologyStore = create<TopologyState>()(
  persist(
    (set, get) => ({
      name: EMPTY_NAME,
      devices: [],
      links: [],
      selectedDeviceId: null,
      selectedLinkId: null,

      addDevice: (presetId, position) => {
        const device = createDevice(presetId, position, get().devices)
        set((state) => ({
          devices: [...state.devices, device],
          selectedDeviceId: device.id,
          selectedLinkId: null,
        }))
        return device
      },

      removeDevice: (deviceId) =>
        set((state) => ({
          devices: state.devices.filter((d) => d.id !== deviceId),
          // Cables to a removed device would dangle, so they go too.
          links: state.links.filter(
            (l) => l.a.device_id !== deviceId && l.b.device_id !== deviceId,
          ),
          selectedDeviceId:
            state.selectedDeviceId === deviceId ? null : state.selectedDeviceId,
        })),

      renameDevice: (deviceId, name) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (d) => ({ ...d, name })),
        })),

      moveDevice: (deviceId, position) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (d) => ({ ...d, position })),
        })),

      updateInterface: (deviceId, interfaceId, patch) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (device) => ({
            ...device,
            interfaces: device.interfaces.map((iface) =>
              iface.id === interfaceId ? { ...iface, ...patch } : iface,
            ),
          })),
        })),

      setGateway: (deviceId, gateway) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (device) => ({
            ...device,
            config: { ...device.config, gateway },
          })),
        })),

      setStaticRoutes: (deviceId, routes) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (device) => ({
            ...device,
            config: { ...device.config, static_routes: routes },
          })),
        })),

      updateConfig: (deviceId, patch) =>
        set((state) => ({
          devices: patchDevice(state.devices, deviceId, (device) => ({
            ...device,
            config: { ...device.config, ...patch },
          })),
        })),

      connect: (sourceDeviceId, targetDeviceId) => {
        const { devices, links } = get()
        if (sourceDeviceId === targetDeviceId) {
          return { ok: false, reason: 'A device cannot be cabled to itself.' }
        }
        const source = devices.find((d) => d.id === sourceDeviceId)
        const target = devices.find((d) => d.id === targetDeviceId)
        if (!source || !target) {
          return { ok: false, reason: 'One of those devices no longer exists.' }
        }

        // Any device can be cabled to any other, any number of times — a
        // server to two switches, two switches to each other twice over. If a
        // device has no spare port, it grows one rather than blocking the cable.
        const sourceGrown = freeInterfaceOrGrow(source, links)
        const targetGrown = freeInterfaceOrGrow(target, links)

        const link = createLink(
          { deviceId: source.id, interfaceId: sourceGrown.interface.id },
          { deviceId: target.id, interfaceId: targetGrown.interface.id },
        )
        set((state) => ({
          devices: state.devices.map((d) => {
            if (d.id === source.id) return sourceGrown.device
            if (d.id === target.id) return targetGrown.device
            return d
          }),
          links: [...state.links, link],
        }))
        return { ok: true, link }
      },

      removeLink: (linkId) =>
        set((state) => ({
          links: state.links.filter((l) => l.id !== linkId),
          selectedLinkId: state.selectedLinkId === linkId ? null : state.selectedLinkId,
        })),

      setLinkStatus: (linkId, status) =>
        set((state) => ({
          links: state.links.map((l) => (l.id === linkId ? { ...l, status } : l)),
        })),

      select: (deviceId, linkId = null) =>
        set({ selectedDeviceId: deviceId, selectedLinkId: linkId }),

      applyDeviceState: (deviceState) =>
        set((state) => ({
          devices: state.devices.map((device) => {
            const learned = deviceState[device.id]
            if (!learned) return device

            const next: Device = {
              ...device,
              runtime: {
                arp_table: learned.arp_table,
                mac_table: learned.mac_table,
                dns_cache: learned.dns_cache ?? {},
                dhcp_leases: learned.dhcp_leases ?? {},
                firewall_hits: learned.firewall_hits ?? {},
              },
            }

            // A DHCP lease genuinely reconfigures the client, so it belongs in
            // the document itself — not just in the learned-state block. This
            // is what makes a wrong pool break the client for good.
            const assigned = learned.assigned
            if (assigned) {
              next.interfaces = device.interfaces.map((iface) =>
                iface.id === assigned.interface_id
                  ? { ...iface, ipv4: assigned.ipv4, netmask: assigned.netmask }
                  : iface,
              )
              next.config = {
                ...device.config,
                gateway: assigned.gateway,
                dns_server: assigned.dns_server,
              }
            }
            return next
          }),
        })),

      clearLearnedTables: () =>
        set((state) => ({
          devices: state.devices.map((device) => ({
            ...device,
            runtime: emptyRuntime(),
          })),
        })),

      loadDocument: (document) =>
        set({
          name: document.name || EMPTY_NAME,
          // Files saved before a field existed simply lack it, so every device
          // is normalised on the way in rather than guarded at every read.
          devices: document.devices.map(normalizeDevice),
          links: document.links,
          selectedDeviceId: null,
          selectedLinkId: null,
        }),

      reset: () =>
        set({
          name: EMPTY_NAME,
          devices: [],
          links: [],
          selectedDeviceId: null,
          selectedLinkId: null,
        }),

      rename: (name) => set({ name }),
    }),
    {
      name: 'netquest.topology',
      version: 1,
      partialize: (state) => ({
        name: state.name,
        devices: state.devices,
        links: state.links,
      }),
    },
  ),
)

/** The document as the API expects it, learned tables included. */
export function toDocument(state = useTopologyStore.getState()): TopologyDocument {
  return {
    version: TOPOLOGY_VERSION,
    name: state.name,
    devices: state.devices,
    links: state.links,
  }
}

/** The document as a saved file: no learned tables, no application state. */
export function toExportDocument(state = useTopologyStore.getState()): TopologyDocument {
  return {
    ...toDocument(state),
    devices: state.devices.map((device) => ({
      ...device,
      runtime: emptyRuntime(),
    })),
  }
}

export function selectedDevice(state: TopologyState): Device | null {
  return state.devices.find((d) => d.id === state.selectedDeviceId) ?? null
}
