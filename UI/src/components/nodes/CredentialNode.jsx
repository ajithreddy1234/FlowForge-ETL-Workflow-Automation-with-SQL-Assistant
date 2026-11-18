import { useState } from 'react'
import { Handle, Position } from '@xyflow/react'
import { KeyRound, X, CheckCircle, AlertCircle, Minimize2, Maximize2 } from 'lucide-react'
import { NODE_COLORS } from '../../constants'
import { useStore } from '../../store'
import NodeRunOverlay from './NodeRunOverlay'

const C = NODE_COLORS.credential

const ring = (s) =>
  s === 'done' ? '#34d399' : s === 'error' ? '#f87171' : s === 'running' ? '#8B5CF6' : C.border

export default function CredentialNode({ id, data }) {
  const removeNode = useStore(s => s.removeNode)
  const updateNodeData = useStore(s => s.updateNodeData)
  const [hovered, setHovered] = useState(false)
  const isConfigured = !!(data.host && data.database && data.username)
  const isConnected = data.connectionStatus === 'connected'
  const connectionFailed = data.connectionStatus === 'error'
  const collapsed = !!data.collapsed
  const selected = data.runStatus === 'running'

  return (
    <div
      className={`w-44 cursor-pointer select-none ${selected ? 'node-running' : ''}`}
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
        className={`overflow-hidden backdrop-blur-sm ${collapsed ? 'rounded-full' : 'rounded-2xl'}`}
        style={{ border: `1.5px solid ${ring(data.runStatus)}`, background: C.bg, position: 'relative', boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}
      >
        <NodeRunOverlay status={data.runStatus} accentColor="#8B5CF6" />

        <div className={`flex items-center gap-2 px-3 py-2 ${collapsed ? '' : ''}`}
          style={{ background: C.header, position: 'relative', zIndex: 3 }}>
          <div className="flex h-4 w-4 items-center justify-center rounded-full bg-white/10">
            <KeyRound size={10} style={{ color: C.text }} />
          </div>
          <span className="text-xs font-semibold" style={{ color: C.text }}>Credential</span>
          {!collapsed && (
            <button
              onClick={e => { e.stopPropagation(); updateNodeData(id, { collapsed: !collapsed }) }}
              title="Minimize node"
              aria-label="Minimize node"
              className="ml-auto rounded p-0.5 text-white/50 hover:bg-white/10"
            >
              <Minimize2 size={10} />
            </button>
          )}
          {collapsed && (
            <button
              onClick={e => { e.stopPropagation(); updateNodeData(id, { collapsed: !collapsed }) }}
              title="Expand node"
              aria-label="Expand node"
              className="ml-auto rounded p-0.5 text-white/50 hover:bg-white/10"
            >
              <Maximize2 size={10} />
            </button>
          )}
          {data.runStatus === 'done' && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-label="Success" />}
          {data.runStatus === 'error' && <span className="h-1.5 w-1.5 rounded-full bg-red-400" aria-label="Error" />}
        </div>

        {!collapsed && (
          <div className="space-y-1 px-3 py-2" style={{ position: 'relative', zIndex: 3 }}>
            {isConnected ? (
              <>
                <div className="flex items-center gap-1">
                  <CheckCircle size={10} className="text-emerald-400" />
                  <p className="text-xs font-medium text-emerald-400">Connected</p>
                </div>
                <p className="truncate font-mono text-[10px] text-white/45">
                  {import.meta.env.VITE_PUBLIC_DEMO === 'true' ? 'synthetic_orders · read only' : `${data.username}@${data.host}/${data.database}`}
                </p>
              </>
            ) : connectionFailed ? (
              <div className="flex items-center gap-1">
                <AlertCircle size={10} className="text-red-400" />
                <p className="text-xs text-red-400">Connection failed</p>
              </div>
            ) : isConfigured ? (
              <div className="flex items-center gap-1">
                <AlertCircle size={10} className="text-amber-400" />
                <p className="text-xs text-amber-300">Check connection</p>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <AlertCircle size={10} className="text-white/30" />
                <p className="text-xs text-white/35">Not configured</p>
              </div>
            )}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Right} id="out" style={{ right: -6 }} />
    </div>
  )
}
