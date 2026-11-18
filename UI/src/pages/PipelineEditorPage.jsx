import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate, useParams, useBlocker } from 'react-router-dom'
import {
  ReactFlow, Background, Controls, MiniMap,
  useReactFlow, ReactFlowProvider,
  reconnectEdge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useStore } from '../store'
import { useAuth } from '../hooks/useAuth'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useToast } from '../components/common/Toast'
import TopBar from '../components/TopBar'
import NodeLibrary from '../components/NodeLibrary'
import PreviewPanel from '../components/PreviewPanel'
import CredentialPanel from '../components/panels/CredentialPanel'
import ExtractPanel from '../components/panels/ExtractPanel'
import TransformPanel from '../components/panels/TransformPanel'
import LoadPanel from '../components/panels/LoadPanel'
import CredentialNode from '../components/nodes/CredentialNode'
import ExtractNode from '../components/nodes/ExtractNode'
import TransformNode from '../components/nodes/TransformNode'
import LoadNode from '../components/nodes/LoadNode'
import DeletableEdge from '../components/edges/DeletableEdge'
import ErrorDialog from '../components/ErrorDialog'
import ConfirmDialog from '../components/common/ConfirmDialog'
import ScheduleModal from '../components/ScheduleModal'
import BottomDock from '../components/layout/BottomDock'
import PipelineOnboarding from '../components/PipelineOnboarding'
import AmbientGlow from '../components/layout/AmbientGlow'
import { reportToGraph } from '../reportImporter'
import * as pipelineApi from '../services/pipelineApi'
import { runPipeline } from '../services/executionApi'
import { ApiError } from '../services/apiClient'
import { validatePipeline } from '../utils/pipelineValidation'
import { PanelLeftOpen, PanelRightClose, PanelRightOpen, MousePointerSquareDashed } from 'lucide-react'

const nodeTypes = {
  credential: CredentialNode,
  extract: ExtractNode,
  transform: TransformNode,
  load: LoadNode,
}

const edgeTypes = { deletable: DeletableEdge }

const MINIMAP_COLORS = {
  credential: 'rgba(255,255,255,0.4)',
  extract: '#60a5fa',
  transform: '#fb923c',
  load: '#34d399',
}

const CLIPBOARD_KEY = 'etl-pipeline-copy-buffer'
const SETTINGS_PANEL_MIN_WIDTH = 340
const SETTINGS_PANEL_MAX_WIDTH = 760

function EditorCanvas({ savedName }) {
  const {
    nodes, edges,
    onNodesChange, onEdgesChange, onConnect,
    addNode, selectNode, updateNodeData,
    getGraph, clearRunStatus, setRunStatus,
    selectedNodeId, undo, redo,
    removeEdge,
    getCopiedGraph, dirty, currentPipelineKey, pipelineName, loadGraph,
  } = useStore()

  const navigate = useNavigate()
  const { user, requireLogin } = useAuth()
  const toast = useToast()
  const { screenToFlowPosition, getIntersectingNodes, fitView } = useReactFlow()
  const isCompact = useMediaQuery('(max-width: 1023px)')

  const [running, setRunning] = useState(false)
  const [pipelineErrors, setPipelineErrors] = useState([])
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [nodeLibraryCollapsed, setNodeLibraryCollapsed] = useState(isCompact)
  const [rightPanelWidth, setRightPanelWidth] = useState(SETTINGS_PANEL_MIN_WIDTH)
  const [resizingSettings, setResizingSettings] = useState(false)
  const [areaCopyActive, setAreaCopyActive] = useState(false)
  const [areaCopyBox, setAreaCopyBox] = useState(null)
  const [areaCopyMessage, setAreaCopyMessage] = useState('')
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [onboardingDismissed, setOnboardingDismissed] = useState(false)
  const edgeReconnectRef = useRef(true)
  const canvasRef = useRef(null)
  const addCascadeRef = useRef(0)
  // Captured once: whether this pipeline had nodes when the canvas first
  // mounted. `fitView` must stay a stable boolean — if it flips true the
  // instant the first node is added, React Flow re-fits (and re-zooms)
  // mid-session, throwing off every subsequent screenToFlowPosition call.
  const hadInitialNodesRef = useRef(nodes.length > 0)

  // Reads dirty via getState() rather than the closed-over value — a save
  // that calls markSaved() and navigate() in the same tick would otherwise
  // block on a stale `dirty=true` from before React re-renders this hook.
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    useStore.getState().dirty && currentLocation.pathname !== nextLocation.pathname)

  useEffect(() => {
    if (isCompact) setNodeLibraryCollapsed(true)
  }, [isCompact])

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (!dirty) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [dirty])

  useEffect(() => {
    nodes.forEach(n => {
      if (n.type === 'transform') {
        const count = edges.filter(e => e.target === n.id).length
        if (n.data._inputCount !== count) updateNodeData(n.id, { _inputCount: count })
      }
    })
  }, [edges]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape' && areaCopyActive) {
        setAreaCopyActive(false)
        setAreaCopyBox(null)
        setAreaCopyMessage('')
        return
      }
      const mod = e.metaKey || e.ctrlKey
      if (!mod) return
      if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((e.key === 'z' && e.shiftKey) || e.key === 'y') { e.preventDefault(); redo() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, areaCopyActive])

  useEffect(() => {
    if (!areaCopyMessage || areaCopyActive) return
    const t = setTimeout(() => setAreaCopyMessage(''), 2500)
    return () => clearTimeout(t)
  }, [areaCopyMessage, areaCopyActive])

  useEffect(() => {
    if (!resizingSettings) return
    const handleMove = (e) => {
      const nextWidth = window.innerWidth - e.clientX
      setRightPanelWidth(Math.min(SETTINGS_PANEL_MAX_WIDTH, Math.max(SETTINGS_PANEL_MIN_WIDTH, nextWidth)))
    }
    const stop = () => setResizingSettings(false)
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    return () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [resizingSettings])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const type = e.dataTransfer.getData('node-type')
    if (!type) return
    const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    addNode(type, position)
  }, [screenToFlowPosition, addNode])

  const onDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const handleAddNode = useCallback((type) => {
    const bounds = canvasRef.current?.getBoundingClientRect()
    const index = addCascadeRef.current
    addCascadeRef.current += 1
    const col = index % 3
    const row = Math.floor(index / 3)
    const offset = { x: col * 260, y: row * 170 }
    const origin = bounds
      ? { x: bounds.left + 120, y: bounds.top + 100 }
      : { x: 200, y: 120 }
    addNode(type, screenToFlowPosition({ x: origin.x + offset.x, y: origin.y + offset.y }))
  }, [addNode, screenToFlowPosition])

  const onReconnectStart = useCallback(() => { edgeReconnectRef.current = false }, [])
  const onReconnect = useCallback((oldEdge, newConn) => {
    edgeReconnectRef.current = true
    useStore.setState(s => ({ edges: reconnectEdge(oldEdge, newConn, s.edges) }))
  }, [])
  const onReconnectEnd = useCallback((_, edge) => {
    if (!edgeReconnectRef.current) removeEdge(edge.id)
    edgeReconnectRef.current = true
  }, [removeEdge])

  const handleRun = () => {
    if (running) return

    const issues = validatePipeline(nodes, edges)
    if (issues.length > 0) {
      setPipelineErrors(issues)
      return
    }

    clearRunStatus()
    setPipelineErrors([])
    setRunning(true)

    runPipeline(getGraph(), {
      onProgress: (msg) => {
        setRunStatus(msg.node_id, msg.status, msg.error || null)
        if (msg.rows != null) updateNodeData(msg.node_id, { rows: msg.rows })
      },
      onComplete: (errors) => {
        setRunning(false)
        if (errors.length > 0) setPipelineErrors(errors)
        else toast.push('Pipeline ran successfully', { type: 'success' })
      },
      onError: (errors) => {
        setRunning(false)
        setPipelineErrors(errors)
      },
      onAuthRequired: () => {
        setRunning(false)
        requireLogin()
      },
    })
  }

  const createGuidedPipeline = () => {
    const graph = {
      pipeline_name: 'My ETL Pipeline',
      nodes: [
        {
          id: 'credential_1',
          type: 'credential',
          position: { x: 80, y: 180 },
          data: { label: 'Source Database', db_type: 'mysql', connectionStatus: 'idle', runStatus: 'idle' },
        },
        {
          id: 'extract_2',
          type: 'extract',
          position: { x: 390, y: 180 },
          data: { label: 'Describe Your Data', sql: '', runStatus: 'idle' },
        },
        {
          id: 'load_3',
          type: 'load',
          position: { x: 720, y: 180 },
          data: { label: 'Google Sheets Output', tab_names: ['Output'], tab_name: 'Output', runStatus: 'idle' },
        },
      ],
      edges: [
        { id: 'guided_credential_extract', source: 'credential_1', target: 'extract_2', type: 'deletable', animated: true },
        { id: 'guided_extract_load', source: 'extract_2', target: 'load_3', type: 'deletable', animated: true },
      ],
    }
    loadGraph(graph, null)
    useStore.setState({ dirty: true, selectedNodeId: 'credential_1' })
    setOnboardingDismissed(true)
    setRightPanelCollapsed(false)
    setTimeout(() => fitView({ duration: 350, padding: 0.25 }), 0)
  }

  const selectedNode = nodes.find(n => n.id === selectedNodeId)
  const handleNodeClick = (_, node) => {
    selectNode(node.id)
    setRightPanelCollapsed(false)
  }

  const startAreaCopy = () => {
    setAreaCopyActive(true)
    setAreaCopyBox(null)
    setAreaCopyMessage('Drag over the nodes you want to copy')
  }

  const areaRect = areaCopyBox ? {
    left: Math.min(areaCopyBox.startLocal.x, areaCopyBox.currentLocal.x),
    top: Math.min(areaCopyBox.startLocal.y, areaCopyBox.currentLocal.y),
    width: Math.abs(areaCopyBox.currentLocal.x - areaCopyBox.startLocal.x),
    height: Math.abs(areaCopyBox.currentLocal.y - areaCopyBox.startLocal.y),
  } : null

  const copyNodesInArea = (start, current) => {
    const a = screenToFlowPosition(start)
    const b = screenToFlowPosition(current)
    const flowRect = {
      x: Math.min(a.x, b.x), y: Math.min(a.y, b.y),
      width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y),
    }
    if (flowRect.width < 8 || flowRect.height < 8) {
      setAreaCopyMessage('Selection is too small')
      return
    }
    const selectedIds = getIntersectingNodes(flowRect, true).map(node => node.id)
    if (!selectedIds.length) {
      setAreaCopyMessage('No nodes inside selection')
      return
    }
    const graph = getCopiedGraph(selectedIds)
    localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(graph))
    setAreaCopyMessage(`Copied ${graph.nodes.length} node${graph.nodes.length === 1 ? '' : 's'} and ${graph.edges.length} edge${graph.edges.length === 1 ? '' : 's'}`)
  }

  const handleAreaPointerDown = (e) => {
    e.preventDefault()
    const bounds = canvasRef.current?.getBoundingClientRect()
    if (!bounds) return
    e.currentTarget.setPointerCapture(e.pointerId)
    const screen = { x: e.clientX, y: e.clientY }
    const local = { x: e.clientX - bounds.left, y: e.clientY - bounds.top }
    setAreaCopyBox({ startScreen: screen, currentScreen: screen, startLocal: local, currentLocal: local })
  }

  const handleAreaPointerMove = (e) => {
    if (!areaCopyBox) return
    const bounds = canvasRef.current?.getBoundingClientRect()
    if (!bounds) return
    const screen = { x: e.clientX, y: e.clientY }
    const local = { x: e.clientX - bounds.left, y: e.clientY - bounds.top }
    setAreaCopyBox(box => box ? { ...box, currentScreen: screen, currentLocal: local } : box)
  }

  const finishAreaCopy = (e) => {
    if (!areaCopyBox) return
    copyNodesInArea(areaCopyBox.startScreen, { x: e.clientX, y: e.clientY })
    setAreaCopyActive(false)
    setAreaCopyBox(null)
  }

  const renderPanel = () => {
    if (!selectedNode) {
      return (
        <div className="flex h-full flex-col items-center justify-center p-6 text-center">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.06] text-white/40">
            <MousePointerSquareDashed size={18} />
          </div>
          <p className="text-sm font-medium text-white/70">Select a node to configure it</p>
          <p className="mt-1 text-xs text-white/35">Click any node on the canvas</p>
        </div>
      )
    }
    const props = { node: selectedNode }
    switch (selectedNode.type) {
      case 'credential': return <CredentialPanel {...props} />
      case 'extract': return <ExtractPanel {...props} />
      case 'transform': return <TransformPanel {...props} />
      case 'load': return <LoadPanel {...props} />
      default: return null
    }
  }

  const defaultEdgeOptions = { type: 'deletable', animated: true }
  const pipelineForSchedule = currentPipelineKey ? { name: currentPipelineKey, pipeline_name: pipelineName } : null

  return (
    <div className="editor-shell flex flex-col bg-void-bg">
      <TopBar
        onRun={handleRun}
        running={running}
        onStartAreaCopy={startAreaCopy}
        onSaved={saved => navigate(`/pipelines/${encodeURIComponent(saved.name)}`, { replace: true })}
        currentUser={user}
        onBack={() => navigate('/pipelines')}
        onFitView={() => fitView({ duration: 300, padding: 0.2 })}
        onOpenSchedule={() => setScheduleOpen(true)}
        onValidationResult={(issues) => setPipelineErrors(issues)}
      />
      {pipelineErrors.length > 0 && (
        <ErrorDialog errors={pipelineErrors} onClose={() => setPipelineErrors([])} />
      )}

      <div className="relative flex flex-1 min-h-0 gap-3 p-3">
        {nodeLibraryCollapsed ? (
          <button
            type="button"
            onClick={() => setNodeLibraryCollapsed(false)}
            title="Show component palette"
            aria-label="Show component palette"
            className="void-glass void-focus flex h-10 w-10 shrink-0 items-center justify-center self-start rounded-xl text-white/60 hover:bg-white/5"
          >
            <PanelLeftOpen size={16} />
          </button>
        ) : (
          <NodeLibrary onCollapse={() => setNodeLibraryCollapsed(true)} onAddNode={handleAddNode} />
        )}

        <div className="relative min-w-0 flex-1 overflow-hidden rounded-2xl border border-white/[0.06]" ref={canvasRef}>
          <AmbientGlow position="top" size={520} className="opacity-40" />
          {nodes.length === 0 && !onboardingDismissed && (
            <PipelineOnboarding
              onGuidedStart={createGuidedPipeline}
              onBlankStart={() => setOnboardingDismissed(true)}
            />
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onReconnectStart={onReconnectStart}
            onReconnect={onReconnect}
            onReconnectEnd={onReconnectEnd}
            onNodeClick={handleNodeClick}
            onPaneClick={() => selectNode(null)}
            onDrop={onDrop}
            onDragOver={onDragOver}
            fitView={hadInitialNodesRef.current}
            defaultViewport={{ x: 0, y: 0, zoom: 1 }}
            minZoom={0.3}
            deleteKeyCode="Delete"
            proOptions={{ hideAttribution: true }}
          >
            <Background color="rgba(139,92,246,0.35)" gap={28} size={1} variant="dots" />
            <Controls />
            <MiniMap nodeColor={n => MINIMAP_COLORS[n.type] || 'rgba(255,255,255,0.4)'} maskColor="rgba(10,10,10,0.75)" style={{ width: 140, height: 95 }} />
          </ReactFlow>

          {areaCopyActive && (
            <div
              className="absolute inset-0 z-40"
              onPointerDown={handleAreaPointerDown}
              onPointerMove={handleAreaPointerMove}
              onPointerUp={finishAreaCopy}
              onPointerCancel={() => { setAreaCopyActive(false); setAreaCopyBox(null); setAreaCopyMessage('') }}
              style={{ cursor: 'crosshair', background: 'rgba(0,0,0,0.15)' }}
            >
              <div className="void-glass absolute left-3 top-3 rounded-lg px-3 py-2 text-xs font-medium text-white">
                {areaCopyMessage || 'Drag over the nodes you want to copy'}
              </div>
              {areaRect && (
                <div className="absolute rounded-sm" style={{ left: areaRect.left, top: areaRect.top, width: areaRect.width, height: areaRect.height, background: 'rgba(139,92,246,0.15)', border: '1.5px solid #8B5CF6' }} />
              )}
            </div>
          )}
          {!areaCopyActive && areaCopyMessage && (
            <div className="void-glass absolute left-3 top-3 z-30 rounded-lg px-3 py-2 text-xs font-medium text-white">
              {areaCopyMessage}
            </div>
          )}
        </div>

        {isCompact ? (
          selectedNode && (
            <>
              <div
                className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                onClick={() => selectNode(null)}
                aria-hidden="true"
              />
              <div className="void-glass fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col shadow-[0_0_60px_rgba(0,0,0,0.6)]">
                <div className="flex items-center justify-between border-b border-white/[0.07] px-3 py-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-white/70">Node Properties</span>
                  <button type="button" onClick={() => selectNode(null)} title="Close node properties" aria-label="Close node properties" className="void-focus rounded-lg p-1.5 text-white/50 hover:bg-white/5">
                    <PanelRightClose size={14} />
                  </button>
                </div>
                <div className="border-b border-white/[0.07] px-3 py-2 font-mono text-[10px] text-white/30">
                  id: {selectedNode.id}
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">{renderPanel()}</div>
                <PreviewPanel selectedNodeId={selectedNodeId} />
              </div>
            </>
          )
        ) : rightPanelCollapsed ? (
          <button
            type="button"
            onClick={() => setRightPanelCollapsed(false)}
            title="Show node properties"
            aria-label="Show node properties"
            className="void-glass void-focus flex h-10 w-10 shrink-0 items-center justify-center self-start rounded-xl text-white/60 hover:bg-white/5"
          >
            <PanelRightOpen size={16} />
          </button>
        ) : (
          <div className="void-glass relative flex shrink-0 flex-col rounded-2xl" style={{ width: rightPanelWidth, minWidth: SETTINGS_PANEL_MIN_WIDTH, maxWidth: SETTINGS_PANEL_MAX_WIDTH }}>
            <div
              role="separator"
              aria-orientation="vertical"
              title="Drag to widen node properties"
              onPointerDown={(e) => { e.preventDefault(); setResizingSettings(true) }}
              className="absolute bottom-0 top-0 z-20"
              style={{ left: -6, width: 8, cursor: 'col-resize', background: resizingSettings ? 'rgba(139,92,246,0.2)' : 'transparent' }}
            />
            <div className="flex items-center justify-between border-b border-white/[0.07] px-3 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-white/70">Node Properties</span>
              <button type="button" onClick={() => setRightPanelCollapsed(true)} title="Hide node properties" aria-label="Hide node properties" className="void-focus rounded-lg p-1.5 text-white/50 hover:bg-white/5">
                <PanelRightClose size={14} />
              </button>
            </div>
            {selectedNode && (
              <div className="border-b border-white/[0.07] px-3 py-2 font-mono text-[10px] text-white/30">
                id: {selectedNode.id}
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-y-auto">{renderPanel()}</div>
            {selectedNode && <PreviewPanel selectedNodeId={selectedNodeId} />}
          </div>
        )}
      </div>

      <div className="flex justify-center pb-3">
        <BottomDock />
      </div>

      {scheduleOpen && pipelineForSchedule && (
        <ScheduleModal pipeline={pipelineForSchedule} currentUser={user} onClose={() => setScheduleOpen(false)} />
      )}

      <ConfirmDialog
        open={blocker.state === 'blocked'}
        title="Leave without saving?"
        description="This pipeline has unsaved changes. If you leave now, those changes will be lost."
        confirmLabel="Leave"
        danger
        onConfirm={() => blocker.proceed?.()}
        onCancel={() => blocker.reset?.()}
      />
    </div>
  )
}

export default function PipelineEditorPage() {
  const { pipelineId } = useParams()
  const navigate = useNavigate()
  const loadGraph = useStore(s => s.loadGraph)
  const newPipeline = useStore(s => s.newPipeline)
  const loadedKeyRef = useRef(null)
  const [status, setStatus] = useState(pipelineId ? 'loading' : 'ready')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!pipelineId) {
      if (loadedKeyRef.current !== null) newPipeline()
      loadedKeyRef.current = null
      setStatus('ready')
      return
    }
    // Already loaded in this session, or the graph in memory is the one we
    // just saved (TopBar sets currentPipelineKey before navigating here) —
    // skip a redundant round trip that would blow away in-memory state.
    if (loadedKeyRef.current === pipelineId || useStore.getState().currentPipelineKey === pipelineId) {
      loadedKeyRef.current = pipelineId
      setStatus('ready')
      return
    }
    let cancelled = false
    setStatus('loading')
    pipelineApi.getPipeline(pipelineId)
      .then(report => {
        if (cancelled) return
        loadGraph(reportToGraph(report), pipelineId)
        loadedKeyRef.current = pipelineId
        setStatus('ready')
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load this pipeline.')
        setStatus('error')
      })
    return () => { cancelled = true }
  }, [pipelineId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (status === 'loading') {
    return <div className="editor-shell flex items-center justify-center bg-void-bg text-sm text-white/50">Loading pipeline…</div>
  }
  if (status === 'error') {
    return (
      <div className="editor-shell flex items-center justify-center bg-void-bg p-6">
        <div className="void-glass max-w-md rounded-2xl p-6 text-center">
          <h1 className="mb-2 text-base font-bold text-white">Pipeline could not be opened</h1>
          <p className="mb-4 text-sm text-white/50">{error}</p>
          <button onClick={() => navigate('/pipelines')} className="void-focus rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover">
            Back to Pipelines
          </button>
        </div>
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <EditorCanvas />
    </ReactFlowProvider>
  )
}
