import { EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import { memo, useRef } from 'react'

import { shortCableLabel } from '@/lib/cableLabel'
import { TONE_HEX, packetTone } from '@/lib/packets'
import { useSimulationStore } from '@/stores/simulationStore'
import { useTopologyStore } from '@/stores/topologyStore'

/**
 * A cable, plus the packet currently crossing it.
 *
 * Rendered as a bezier curve — leaving each node from the side its handle
 * actually sits on — rather than a dead-straight line, so several cables
 * converging on one device fan out instead of stacking into a single point.
 *
 * The travelling dot is positioned with `getPointAtLength` on the real
 * rendered path rather than a linear guess, so it stays glued to the curve
 * no matter how it bends.
 */
function CableEdgeComponent({
  id,
  source,
  sourceX,
  sourceY,
  sourcePosition,
  targetX,
  targetY,
  targetPosition,
  selected,
}: EdgeProps) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.3,
  })

  const pathRef = useRef<SVGPathElement>(null)

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

  let dotX = sourceX
  let dotY = sourceY
  if (transit && pathRef.current) {
    const length = pathRef.current.getTotalLength()
    const point = pathRef.current.getPointAtLength(t * length)
    dotX = point.x
    dotY = point.y
  }

  const stroke = isDown ? 'var(--color-bad)' : selected ? 'var(--color-accent)' : 'var(--color-line)'

  const portLabel = link && selected ? shortCableLabel(link, devices) : null

  return (
    <>
      {/* Invisible fat path so the cable is easy to click; also what the dot tracks. */}
      <path ref={pathRef} d={path} fill="none" stroke="transparent" strokeWidth={16} />
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
