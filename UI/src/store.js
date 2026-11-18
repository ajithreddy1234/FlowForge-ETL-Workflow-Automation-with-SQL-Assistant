import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'

let nodeIdCounter = 1
export const newId = (type) => `${type}_${nodeIdCounter++}`

const MAX_HISTORY = 50

function snap(s) {
  return {
    nodes: s.nodes.map(n => ({ ...n, data: { ...n.data } })),
    edges: s.edges.map(e => ({ ...e })),
  }
}

function cloneGraph(nodes, edges) {
  return {
    nodes: nodes.map(n => ({ ...n, position: { ...n.position }, data: { ...n.data } })),
    edges: edges.map(e => ({ ...e })),
  }
}

function withoutSecrets(node) {
  const data = { ...(node.data || {}) }
  delete data.password
  delete data.encrypted_password
  return { ...node, position: { ...(node.position || {}) }, data }
}

function bumpNodeCounter(nodes) {
  const maxId = nodes.reduce((max, node) => {
    const match = String(node.id || '').match(/_(\d+)$/)
    return match ? Math.max(max, Number(match[1])) : max
  }, 0)
  nodeIdCounter = Math.max(nodeIdCounter, maxId + 1)
}

export const useStore = create(
  persist(
    (set, get) => ({
      nodes:          [],
      edges:          [],
      selectedNodeId: null,
      previewData:    {},
      runStatus:      {},
      pipelineName:   'Untitled Pipeline',
      currentPipelineKey: null,
      history:        [],
      future:         [],
      dirty:          false,

      markSaved: () => set({ dirty: false }),

      // ── History ────────────────────────────────────────────────────────────
      _push: () => {
        const s = get()
        set({ history: [...s.history.slice(-MAX_HISTORY + 1), snap(s)], future: [], dirty: true })
      },

      undo: () => {
        const { history, future } = get()
        if (!history.length) return
        const prev = history[history.length - 1]
        set({
          nodes:         prev.nodes,
          edges:         prev.edges,
          history:       history.slice(0, -1),
          future:        [snap(get()), ...future],
          selectedNodeId: null,
        })
      },

      redo: () => {
        const { history, future } = get()
        if (!future.length) return
        const next = future[0]
        set({
          nodes:         next.nodes,
          edges:         next.edges,
          history:       [...history, snap(get())],
          future:        future.slice(1),
          selectedNodeId: null,
        })
      },

      // ── React Flow handlers ───────────────────────────────────────────────
      onNodesChange: (changes) => {
        const meaningful = changes.some(c => (c.type === 'position' && c.dragging === false) || c.type === 'remove')
        set(s => ({ nodes: applyNodeChanges(changes, s.nodes), dirty: s.dirty || meaningful }))
      },

      onEdgesChange: (changes) => {
        const meaningful = changes.some(c => c.type === 'remove')
        set(s => ({ edges: applyEdgeChanges(changes, s.edges), dirty: s.dirty || meaningful }))
      },

      onConnect: (conn) => {
        get()._push()
        set(s => ({
          edges: addEdge({ ...conn, animated: true, type: 'deletable' }, s.edges),
        }))
      },

      // ── Node management ───────────────────────────────────────────────────
      addNode: (type, position) => {
        get()._push()
        const id = newId(type)
        const label = type === 'load' ? 'Sink' : type.charAt(0).toUpperCase() + type.slice(1)
        set(s => ({
          nodes: [...s.nodes, {
            id,
            type,
            position,
            data: { label, runStatus: 'idle', ...(import.meta.env.VITE_PUBLIC_DEMO === 'true' && type === 'credential' ? {connection_id:1, host:'sandbox', database:'synthetic_orders', username:'demo', connectionStatus:'connected'} : {}), ...(import.meta.env.VITE_PUBLIC_DEMO === 'true' && type === 'load' ? {google_sheet_url:'sandbox://csv',tab_names:['output'],write_mode:'overwrite'} : {}) },
          }],
        }))
      },

      removeNode: (id) => {
        get()._push()
        set(s => ({
          nodes:          s.nodes.filter(n => n.id !== id),
          edges:          s.edges.filter(e => e.source !== id && e.target !== id),
          selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
        }))
      },

      removeEdge: (id) => {
        get()._push()
        set(s => ({ edges: s.edges.filter(e => e.id !== id) }))
      },

      selectNode: (id) => set({ selectedNodeId: id }),

      updateNodeData: (id, patch) =>
        set(s => ({
          nodes: s.nodes.map(n =>
            n.id === id ? { ...n, data: { ...n.data, ...patch } } : n
          ),
          dirty: true,
        })),

      // ── Preview ───────────────────────────────────────────────────────────
      setPreviewData: (nodeId, data) =>
        set(s => ({ previewData: { ...s.previewData, [nodeId]: data } })),

      // ── Run status ─────────────────────────────────────────────────────────
      setRunStatus: (nodeId, status, error = null) =>
        set(s => ({
          runStatus: { ...s.runStatus, [nodeId]: status },
          nodes: s.nodes.map(n =>
            n.id === nodeId
              ? { ...n, data: { ...n.data, runStatus: status, runError: error } }
              : n
          ),
        })),

      clearRunStatus: () =>
        set(s => ({
          runStatus: {},
          nodes: s.nodes.map(n => ({
            ...n, data: { ...n.data, runStatus: 'idle', runError: null },
          })),
        })),

      setPipelineName: (name) => set({ pipelineName: name }),
      setCurrentPipelineKey: (name) => set({ currentPipelineKey: name || null }),

      loadGraph: (graph, savedKey = null) => {
        const nodes = graph.nodes || []
        const edges = graph.edges || []
        bumpNodeCounter(nodes)
        set({
          nodes,
          edges,
          pipelineName: graph.pipeline_name || graph.pipelineName || 'Untitled Pipeline',
          currentPipelineKey: savedKey,
          selectedNodeId: null,
          previewData: {},
          runStatus: {},
          history: [],
          future: [],
          dirty: false,
        })
      },

      newPipeline: () => {
        get()._push()
        set({
          nodes: [],
          edges: [],
          pipelineName: 'Untitled Pipeline',
          currentPipelineKey: null,
          selectedNodeId: null,
          previewData: {},
          runStatus: {},
          future: [],
          dirty: false,
        })
      },

      getCanvasGraph: () => {
        const { nodes, edges, pipelineName } = get()
        return { pipeline_name: pipelineName, ...cloneGraph(nodes, edges) }
      },

      getCopiedGraph: (nodeIds = null) => {
        const { nodes, edges, pipelineName } = get()
        if (!nodeIds) {
          return {
            pipeline_name: pipelineName,
            nodes: nodes.map(withoutSecrets),
            edges: edges.map(edge => ({ ...edge })),
          }
        }

        const include = new Set(nodeIds)
        const copiedNodes = nodes.filter(node => include.has(node.id))
        const copiedEdges = edges.filter(edge => include.has(edge.source) && include.has(edge.target))
        return {
          pipeline_name: `${pipelineName} Copy`,
          nodes: copiedNodes.map(withoutSecrets),
          edges: copiedEdges.map(edge => ({ ...edge })),
        }
      },

      pasteGraph: (graph) => {
        const copiedNodes = graph.nodes || []
        const copiedEdges = graph.edges || []
        if (!copiedNodes.length) return

        get()._push()
        set(s => {
          const idMap = {}
          const now = Date.now()
          const pastedNodes = copiedNodes.map(node => {
            const safeNode = withoutSecrets(node)
            const id = `${node.type || 'node'}_${nodeIdCounter++}`
            idMap[node.id] = id
            return {
              ...safeNode,
              id,
              selected: false,
              position: {
                x: (node.position?.x || 0) + 48,
                y: (node.position?.y || 0) + 48,
              },
              data: {
                ...(node.data || {}),
                runStatus: 'idle',
                runError: null,
              },
            }
          })
          const pastedEdges = copiedEdges
            .filter(edge => idMap[edge.source] && idMap[edge.target])
            .map((edge, index) => ({
              ...edge,
              id: `copied_edge_${now}_${index}`,
              source: idMap[edge.source],
              target: idMap[edge.target],
              selected: false,
              animated: edge.animated ?? true,
              type: edge.type || 'deletable',
            }))
          return {
            nodes: [...s.nodes, ...pastedNodes],
            edges: [...s.edges, ...pastedEdges],
            selectedNodeId: pastedNodes[0]?.id || null,
          }
        })
      },

      // ── Serialise to graph for API ────────────────────────────────────────
      getGraph: () => {
        const { nodes, edges, pipelineName } = get()
        return { pipeline_name: pipelineName, nodes, edges }
      },

      // ── Helpers ───────────────────────────────────────────────────────────
      getInputCount: (nodeId) =>
        get().edges.filter(e => e.target === nodeId).length,

      getUpstreamId: (nodeId, handle = null) => {
        const edges = get().edges
        if (handle) {
          return edges.find(e => e.target === nodeId && e.targetHandle === handle)?.source ?? null
        }
        return edges.find(e => e.target === nodeId)?.source ?? null
      },

      getConnectedCredential: (extractNodeId) => {
        const { nodes, edges } = get()
        const inEdge = edges.find(e => e.target === extractNodeId)
        if (!inEdge) return null
        const src = nodes.find(n => n.id === inEdge.source)
        return src?.type === 'credential' ? src : null
      },
    }),
    {
      name: 'etl-pipeline-state',
      storage: createJSONStorage(() => localStorage),
      // Only persist the canvas state — not transient UI state
      partialize: (state) => ({
        nodes:        state.nodes.map(withoutSecrets),
        edges:        state.edges,
        pipelineName: state.pipelineName,
        currentPipelineKey: state.currentPipelineKey,
      }),
      // Restored nodes carry ids like "credential_3" — without this the
      // in-memory counter would restart at 1 and hand out colliding ids
      // to newly added nodes after a page reload.
      onRehydrateStorage: () => (state) => {
        if (state?.nodes?.length) {
          state.nodes = state.nodes.map(withoutSecrets)
          bumpNodeCounter(state.nodes)
          // Trigger persistence once initialization completes so passwords
          // saved by older releases are removed from localStorage as well.
          setTimeout(() => {
            const current = useStore.getState()
            useStore.setState({ nodes: current.nodes.map(withoutSecrets) })
          }, 0)
        }
      },
    }
  )
)
