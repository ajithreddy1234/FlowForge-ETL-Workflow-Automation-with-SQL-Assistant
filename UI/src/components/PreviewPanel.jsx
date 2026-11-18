import { useEffect, useState } from 'react'
import { Eye, RefreshCw, AlertTriangle, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react'
import { useStore } from '../store'
import * as connectionApi from '../services/connectionApi'
import { ApiError } from '../services/apiClient'

export default function PreviewPanel({ selectedNodeId }) {
  const {
    getGraph, setPreviewData, previewData, nodes, getConnectedCredential, updateNodeData,
  } = useStore()
  const [loading, setLoading] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  const data = selectedNodeId ? previewData[selectedNodeId] : null
  const selectedNode = nodes.find(n => n.id === selectedNodeId)
  const isExtract = selectedNode?.type === 'extract'
  const isCredential = selectedNode?.type === 'credential'
  const credential = isExtract ? getConnectedCredential(selectedNodeId) : null
  const credentialMissingFields = isCredential && !selectedNode?.data?.connection_id && !(
    selectedNode?.data?.host && selectedNode?.data?.database && selectedNode?.data?.username
  )
  const previewBlocked = isExtract && (!credential || credential.data?.connectionStatus !== 'connected')

  useEffect(() => {
    setCollapsed(false)
  }, [selectedNodeId])

  const checkCredentialConnection = async () => {
    updateNodeData(selectedNodeId, {
      connectionStatus: 'checking',
      connectionError: null,
      runStatus: 'running',
      runError: null,
    })
    const res = selectedNode.data?.connection_id
      ? await connectionApi.checkSavedConnection(selectedNode.data.connection_id)
      : await connectionApi.checkDbConnection({
          db_type: selectedNode.data?.db_type || 'mysql',
          host: selectedNode.data?.host || '',
          port: selectedNode.data?.port || '',
          database: selectedNode.data?.database || '',
          username: selectedNode.data?.username || '',
          password: selectedNode.data?.password || '',
        })
    updateNodeData(selectedNodeId, {
      connectionStatus: 'connected',
      connectionError: null,
      connectionMessage: res?.message || 'Database connection successful',
      runStatus: 'done',
      runError: null,
    })
    setPreviewData(selectedNodeId, {
      columns: [],
      rows: [],
      total_rows: 0,
      message: res?.message || 'Database connection successful',
      error: null,
    })
  }

  const handlePreview = async () => {
    if (!selectedNodeId || loading || previewBlocked || credentialMissingFields) return
    setLoading(true)
    try {
      if (isCredential) {
        await checkCredentialConnection()
      } else {
        const res = await connectionApi.previewNode(getGraph(), selectedNodeId)
        setPreviewData(selectedNodeId, res)
      }
      setCollapsed(false)
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (e.message || (isCredential ? 'Connection failed' : 'Preview failed'))
      if (isCredential) {
        updateNodeData(selectedNodeId, {
          connectionStatus: 'error',
          connectionError: message,
          runStatus: 'error',
          runError: message,
        })
      }
      setPreviewData(selectedNodeId, {
        error: message,
        columns: [],
        rows: [],
        total_rows: 0,
      })
      setCollapsed(false)
    } finally {
      setLoading(false)
    }
  }

  const btnDisabled = !selectedNodeId || loading || previewBlocked || credentialMissingFields
  const canToggle = !!data && !loading
  const actionLabel = isCredential ? 'Check Connection' : 'Preview'

  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', background: '#111111' }}>
      <div
        className="flex items-center justify-between px-3 py-2"
        onClick={() => canToggle && setCollapsed(v => !v)}
        title={canToggle ? (collapsed ? 'Show details' : 'Hide details') : undefined}
        style={{
          borderBottom: data && !collapsed ? '1px solid rgba(255,255,255,0.08)' : 'none',
          cursor: canToggle ? 'pointer' : 'default',
        }}
      >
        <div className="flex items-center gap-1.5">
          {canToggle
            ? collapsed
              ? <ChevronUp size={13} className="text-white/45" />
              : <ChevronDown size={13} className="text-white/45" />
            : <Eye size={13} className="text-white/45" />
          }
          <span className="text-xs font-semibold text-white/70">
            {isCredential ? 'Connection Check' : 'Data Preview'}
          </span>
          {data?.total_rows != null && !data.error && !isCredential && (
            <span
              className="rounded-full px-1.5 py-0.5 text-xs font-semibold"
              style={{ background: 'rgba(16,185,129,0.12)', color: '#34d399' }}
            >
              {data.total_rows} rows
            </span>
          )}
          {data && collapsed && (
            <span className="text-xs text-white/35">Hidden</span>
          )}
        </div>

        <button
          onClick={e => {
            e.stopPropagation()
            handlePreview()
          }}
          disabled={btnDisabled}
          title={
            credentialMissingFields
              ? 'Fill Host, Database, and Username first'
              : previewBlocked
                ? 'Check the connected Credential node first'
                : isCredential
                  ? 'Check database connection'
                  : 'Preview data'
          }
          className="void-focus flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all"
          style={{
            background: btnDisabled ? 'rgba(255,255,255,0.06)' : '#8B5CF6',
            color: btnDisabled ? 'rgba(255,255,255,0.3)' : '#fff',
            cursor: btnDisabled ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading
            ? <><RefreshCw size={11} className="animate-spin" /> {isCredential ? 'Checking...' : 'Running...'}</>
            : isCredential
              ? <><CheckCircle size={11} /> {actionLabel}</>
              : <><Eye size={11} /> {actionLabel}</>
          }
        </button>
      </div>

      {!collapsed && previewBlocked && (
        <div className="mx-2 mb-1 mt-2 flex items-start gap-2 rounded-md px-2.5 py-2"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
          <AlertTriangle size={12} style={{ color: '#fbbf24', marginTop: 1, flexShrink: 0 }} />
          <p className="text-xs" style={{ color: '#fbbf24' }}>
            Connect and check a Credential node before previewing.
          </p>
        </div>
      )}

      {!collapsed && data?.error && (
        <div className="m-2 rounded-md px-3 py-2 text-xs" style={{ background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}>
          <strong>Error:</strong> {data.error}
        </div>
      )}

      {!collapsed && data?.columns?.length > 0 && (
        <div style={{ overflowX: 'auto', maxHeight: 240 }}>
          <table className="w-full border-collapse text-xs" style={{ minWidth: 'max-content' }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
              <tr style={{ background: '#171717' }}>
                {data.columns.map(c => (
                  <th
                    key={c}
                    className="whitespace-nowrap px-3 py-1.5 text-left font-semibold"
                    style={{ color: 'rgba(255,255,255,0.6)', borderBottom: '2px solid rgba(255,255,255,0.1)', borderRight: '1px solid rgba(255,255,255,0.06)' }}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}
                  className="transition-colors hover:bg-accent/[0.06]">
                  {data.columns.map(c => (
                    <td
                      key={c}
                      className="whitespace-nowrap px-3 py-1.5 font-mono"
                      style={{ color: 'rgba(255,255,255,0.8)', borderBottom: '1px solid rgba(255,255,255,0.05)', borderRight: '1px solid rgba(255,255,255,0.05)' }}
                    >
                      {row[c] ?? <span style={{ color: 'rgba(255,255,255,0.25)' }}>null</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!collapsed && !data && !loading && !previewBlocked && (
        <div className="px-3 py-3 text-center">
          <p className="text-xs text-white/35">
            {selectedNodeId
              ? isCredential
                ? 'Click Check Connection to verify these database credentials.'
                : 'Click Preview to run up to this node and see the data it produces.'
              : 'Select a node first, then click Preview.'}
          </p>
        </div>
      )}

      {!collapsed && data && !data.error && data.columns?.length === 0 && (
        <div className="px-3 py-3 text-center">
          <p className="text-xs text-white/35">
            {data.message || 'This node produced no output.'}
          </p>
        </div>
      )}
    </div>
  )
}
