import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type Connection,
  useReactFlow,
} from '@xyflow/react'
import { useCallback, useMemo, type DragEvent } from 'react'

import { DEVICE_PROFILES } from '@/lib/devices'
import { useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'
import type { DeviceType } from '@/types'

import { CableEdge } from './CableEdge'
import { DeviceNode, type DeviceNodeData } from './DeviceNode'
import { PALETTE_MIME } from './DevicePalette'

const nodeTypes = { device: DeviceNode }
const edgeTypes = { cable: CableEdge }

const MINIMAP_COLOURS: Record<DeviceType, string> = {
  pc: '#60a5fa',
  switch: '#a78bfa',
  router: '#fbbf24',
  server: '#34d399',
}

export function Canvas() {
  const devices = useTopologyStore((state) => state.devices)
  const links = useTopologyStore((state) => state.links)
  const selectedDeviceId = useTopologyStore((state) => state.selectedDeviceId)
  const selectedLinkId = useTopologyStore((state) => state.selectedLinkId)

  const moveDevice = useTopologyStore((state) => state.moveDevice)
  const removeDevice = useTopologyStore((state) => state.removeDevice)
  const removeLink = useTopologyStore((state) => state.removeLink)
  const connect = useTopologyStore((state) => state.connect)
  const select = useTopologyStore((state) => state.select)
  const addDevice = useTopologyStore((state) => state.addDevice)

  const notify = useUiStore((state) => state.notify)
  const { screenToFlowPosition } = useReactFlow()

  const nodes = useMemo<Node<DeviceNodeData>[]>(
    () =>
      devices.map((device) => ({
        id: device.id,
        type: 'device',
        position: device.position,
        data: { deviceId: device.id },
        selected: device.id === selectedDeviceId,
      })),
    [devices, selectedDeviceId],
  )

  const edges = useMemo<Edge[]>(
    () =>
      links.map((link) => ({
        id: link.id,
        source: link.a.device_id,
        target: link.b.device_id,
        type: 'cable',
        selected: link.id === selectedLinkId,
      })),
    [links, selectedLinkId],
  )

  const onNodesChange = useCallback(
    (changes: NodeChange<Node<DeviceNodeData>>[]) => {
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          moveDevice(change.id, change.position)
        }
      }
    },
    [moveDevice],
  )

  const onEdgesChange = useCallback((_changes: EdgeChange[]) => {
    // Edges are derived from links; removal is handled by onEdgesDelete.
  }, [])

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return
      const result = connect(connection.source, connection.target)
      if (!result.ok) notify(result.reason, 'error')
    },
    [connect, notify],
  )

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }, [])

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()
      const type = event.dataTransfer.getData(PALETTE_MIME) as DeviceType
      if (!type || !(type in DEVICE_PROFILES)) return
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      // Drop point is the cursor; nudge so the node centres under it.
      addDevice(type, { x: position.x - 76, y: position.y - 22 })
    },
    [addDevice, screenToFlowPosition],
  )

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodesDelete={(deleted) => deleted.forEach((node) => removeDevice(node.id))}
      onEdgesDelete={(deleted) => deleted.forEach((edge) => removeLink(edge.id))}
      onNodeClick={(_, node) => select(node.id)}
      onEdgeClick={(_, edge) => select(null, edge.id)}
      onPaneClick={() => select(null, null)}
      onDrop={onDrop}
      onDragOver={onDragOver}
      // Loose mode lets any handle join any other, so users aim at a device
      // rather than hunting for the one correct port.
      connectionMode={ConnectionMode.Loose}
      connectionRadius={34}
      fitView
      fitViewOptions={{ padding: 0.35, maxZoom: 1.2 }}
      minZoom={0.2}
      maxZoom={2.5}
      proOptions={{ hideAttribution: false }}
      deleteKeyCode={['Backspace', 'Delete']}
      className="bg-base"
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={22}
        size={1}
        color="var(--color-line-soft)"
      />
      <Controls
        showInteractive={false}
        className="!border !border-line !bg-panel !shadow-lg"
      />
      <MiniMap
        pannable
        zoomable
        nodeStrokeWidth={0}
        maskColor="rgba(9, 12, 17, 0.75)"
        nodeColor={(node) => {
          const device = devices.find((d) => d.id === node.id)
          return device ? MINIMAP_COLOURS[device.type] : '#64748b'
        }}
      />
    </ReactFlow>
  )
}
