import { useState } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Database, X, AlertTriangle, Minimize2, Maximize2 } from 'lucide-react'
import { NODE_COLORS } from '../../constants'
import { useStore } from '../../store'
import NodeRunOverlay from './NodeRunOverlay'

const C = NODE_COLORS.extract

const ring = (s) =>
  s === 'done' ? '#34d399' : s === 'error' ? '#f87171' : s === 'running' ? '#8B5CF6' : C.border

export default function ExtractNode({ id, data }) {
  const removeNode             = useStore(s => s.removeNode)
  const updateNodeData         = useStore(s => s.updateNodeData)
  const getConnectedCredential = useStore(s => s.getConnectedCredential)
  const [hovered, setHovered]  = useState(false)
  const collapsed = !!data.collapsed

  const sqlPreview = data.sql
    ? data.sql.replace(/\s+/g, ' ').slice(0, 40) + (data.sql.length > 40 ? '...' : '')
    : 'No SQL yet'
  const credential = getConnectedCredential(id)
  const hasCredential = !!credential
  const credentialChecked = credential?.data?.connectionStatus === 'connected'
  const sqlMissing = !(data.sql || '').trim()

  return (
    <div
      className={`w-52 cursor-pointer select-none ${data.runStatus === 'running' ? 'node-running' : ''}`}
      style={{ position: 'relative' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <button
          onClick={e => { e.stopPropagation(); removeNode(id) }}
          title="Delete node"
          aria-label="Delete node"
          style={{
            position: 'absolute', top: -8, right: -8, zIndex: 20,
            width: 18, height: 18, background: '#f87171',
            border: '2px solid #0A0A0A', borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
          }}
        >
          <X size={9} color="#fff" />
        </button>
      )}

      <div
        className={`overflow-hidden ${collapsed ? 'rounded-full' : 'rounded-2xl'}`}
        style={{ border: `1.5px solid ${ring(data.runStatus)}`, background: C.bg, position: 'relative', boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}
      >
        <NodeRunOverlay status={data.runStatus} accentColor="#8B5CF6" />

        <div className="flex items-center gap-2 px-3 py-2"
          style={{ background: C.header, position: 'relative', zIndex: 3 }}>
          <div className="flex h-4 w-4 items-center justify-center rounded-full bg-white/10">
            <Database size={10} style={{ color: C.text }} />
          </div>
          <span className="text-xs font-semibold" style={{ color: C.text }}>Extract</span>
          <button
            onClick={e => { e.stopPropagation(); updateNodeData(id, { collapsed: !collapsed }) }}
            title={collapsed ? 'Expand node' : 'Minimize node'}
            aria-label={collapsed ? 'Expand node' : 'Minimize node'}
            className="ml-auto rounded p-0.5 text-white/50 hover:bg-white/10"
          >
            {collapsed ? <Maximize2 size={10} /> : <Minimize2 size={10} />}
          </button>
          {data.runStatus === 'done' && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-label="Success" />}
          {data.runStatus === 'error' && <span className="h-1.5 w-1.5 rounded-full bg-red-400" aria-label="Error" />}
        </div>

        {!collapsed && (
          <div className="space-y-1 px-3 py-2" style={{ position: 'relative', zIndex: 3 }}>
            <p className="truncate text-xs font-medium text-white">
              {data.label || 'Extract'}
            </p>
            {data.query_date && (
              <p className="font-mono text-[10px] text-blue-300">{data.query_date}</p>
            )}
            {!hasCredential ? (
              <div className="flex items-center gap-1 rounded px-1.5 py-0.5" style={{ background: 'rgba(245,158,11,0.1)' }}>
                <AlertTriangle size={9} className="text-amber-400" />
                <span className="text-[10px] text-amber-300">Connect a Credential</span>
              </div>
            ) : !credentialChecked ? (
              <div className="flex items-center gap-1 rounded px-1.5 py-0.5" style={{ background: 'rgba(245,158,11,0.1)' }}>
                <AlertTriangle size={9} className="text-amber-400" />
                <span className="text-[10px] text-amber-300">Check Credential</span>
              </div>
            ) : sqlMissing ? (
              <div className="flex items-center gap-1 rounded px-1.5 py-0.5" style={{ background: 'rgba(239,68,68,0.1)' }}>
                <AlertTriangle size={9} className="text-red-400" />
                <span className="text-[10px] text-red-300">SQL required</span>
              </div>
            ) : (
              <p className="truncate font-mono text-[10px] text-white/45">{sqlPreview}</p>
            )}
            {data.runStatus === 'done' && data.rows != null && (
              <p className="text-xs font-semibold text-blue-300">{data.rows.toLocaleString()} rows</p>
            )}
            {data.runStatus === 'error' && (
              <p className="truncate text-xs text-red-400">{data.runError}</p>
            )}
          </div>
        )}
      </div>

      <Handle type="target" position={Position.Left} id="in" style={{ left: -6 }} />
      <Handle type="source" position={Position.Right} id="out" style={{ right: -6 }} />
    </div>
  )
}
