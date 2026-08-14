import { EdgeLabelRenderer, getStraightPath, type EdgeProps } from '@xyflow/react'
import { memo } from 'react'

import { shortCableLabel } from '@/lib/cableLabel'
import { TONE_HEX, packetTone } from '@/lib/packets'
import { useSimulationStore } from '@/stores/simulationStore'
import { useTopologyStore } from '@/stores/topologyStore'

/**
 * A cable, plus the packet currently crossing it.
 *
 * Paths are straight, so the travelling dot is a plain interpolation between
 * the two endpoints — no path measurement, and it stays exact at any zoom.
 */
function CableEdgeComponent({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  selected,
}: EdgeProps) {
  const [path, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY })

  const link = useTopologyStore((state) => state.links.find((l) => l.id === id))
  const devices = useTopologyStore((state) => state.devices)
  const transit = useSimulationStore((state) =>
    state.transit?.linkId === id ? state.transit : null,
  )
  const packet = useSimulationStore((state) =>
    transit?.frameUid ? state.packetsByUid[transit.frameUid] : undefined,
  )

  const isDown = link?.status === 'down'
  const tone = packetTone(packet)
  const colour = TONE_HEX[tone]

  // `source` is the React Flow node id, which is the device id.
  const forward = transit ? transit.fromDeviceId === source : true
  const t = transit ? (forward ? transit.progress : 1 - transit.progress) : 0
  const dotX = sourceX + (targetX - sourceX) * t
  const dotY = sourceY + (targetY - sourceY) * t

  const stroke = isDown ? 'var(--color-bad)' : selected ? 'var(--color-accent)' : 'var(--color-line)'

  const portLabel = link && selected ? shortCableLabel(link, devices) : null

  return (
    <>
      {/* Invisible fat path so the cable is easy to click. */}
      <path d={path} fill="none" stroke="transparent" strokeWidth={16} />
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={selected ? 2.5 : 2}
        strokeLinecap="round"
        strokeDasharray={isDown ? '5 6' : undefined}
        className={transit ? 'nq-flowing' : undefined}
      />

      {transit ? (
        <g pointerEvents="none">
          <circle cx={dotX} cy={dotY} r={9} fill={colour} opacity={0.18} />
          <circle cx={dotX} cy={dotY} r={4.5} fill={colour} />
        </g>
      ) : null}

      {isDown || portLabel ? (
        <EdgeLabelRenderer>
          <div
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            className="pointer-events-none absolute rounded border border-line bg-panel px-1.5 py-0.5 font-mono text-[10px] whitespace-nowrap"
          >
            {isDown ? (
              <span className="text-bad">disconnected</span>
            ) : (
              <span className="text-ink-dim">{portLabel}</span>
            )}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  )
}

export const CableEdge = memo(CableEdgeComponent)
