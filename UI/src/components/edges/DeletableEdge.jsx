import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@xyflow/react'
import { X } from 'lucide-react'
import { useStore } from '../../store'

export default function DeletableEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition,
  selected, markerEnd,
}) {
  const removeEdge = useStore(s => s.removeEdge)

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  })

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          strokeWidth: selected ? 2.5 : 1.5,
          stroke: selected ? '#A78BFA' : 'rgba(255,255,255,0.25)',
          transition: 'stroke 0.15s, stroke-width 0.15s',
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
            opacity: selected ? 1 : 0,
            transition: 'opacity 0.15s',
            zIndex: 10,
          }}
          className="nodrag nopan"
        >
          <button
            onClick={(e) => { e.stopPropagation(); removeEdge(id) }}
            title="Remove connection"
            aria-label="Remove connection"
            style={{
              width: 20, height: 20,
              background: '#f87171',
              border: '2px solid #0A0A0A',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
            }}
          >
            <X size={10} color="#fff" />
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
