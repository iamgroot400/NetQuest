/**
 * The topology document — the single source of truth for the whole app.
 *
 * The backend keeps no state: this document is posted with every command and
 * the learned tables that come back are written straight into it.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import { createDevice, createLink, firstFreeInterface } from '@/lib/devices'
import type {
  Device,
  DeviceState,
  DeviceType,
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

  addDevice: (type: DeviceType, position: Position) => Device
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

export const useTopologyStore = create<TopologyState>()(
  persist(
    (set, get) => ({
      name: EMPTY_NAME,
      devices: [],
      links: [],
      selectedDeviceId: null,
      selectedLinkId: null,

      addDevice: (type, position) => {
        const device = createDevice(type, position, get().devices)
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

        const sourcePort = firstFreeInterface(source, links)
        if (!sourcePort) {
          return { ok: false, reason: `${source.name} has no free ports left.` }
        }
        const targetPort = firstFreeInterface(target, links)
        if (!targetPort) {
          return { ok: false, reason: `${target.name} has no free ports left.` }
        }

        const link = createLink(
          { deviceId: source.id, interfaceId: sourcePort.id },
          { deviceId: target.id, interfaceId: targetPort.id },
        )
        set((state) => ({ links: [...state.links, link] }))
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
            return {
              ...device,
              runtime: {
                arp_table: learned.arp_table,
                mac_table: learned.mac_table,
              },
            }
          }),
        })),

      clearLearnedTables: () =>
        set((state) => ({
          devices: state.devices.map((device) => ({
            ...device,
            runtime: { arp_table: {}, mac_table: {} },
          })),
        })),

      loadDocument: (document) =>
        set({
          name: document.name || EMPTY_NAME,
          devices: document.devices.map((device) => ({
            ...device,
            runtime: device.runtime ?? { arp_table: {}, mac_table: {} },
          })),
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
      runtime: { arp_table: {}, mac_table: {} },
    })),
  }
}

export function selectedDevice(state: TopologyState): Device | null {
  return state.devices.find((d) => d.id === state.selectedDeviceId) ?? null
}
