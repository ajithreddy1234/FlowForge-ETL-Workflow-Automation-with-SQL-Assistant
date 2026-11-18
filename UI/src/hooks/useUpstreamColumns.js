import { useState, useEffect } from 'react'
import { useStore } from '../store'
import { apiClient } from '../services/apiClient'

/**
 * Columns produced by the primary (left/first) upstream node of nodeId.
 */
export function useUpstreamColumns(nodeId, handle = null) {
  const [columns, setColumns] = useState([])
  const [loading, setLoading] = useState(false)

  const edges    = useStore(s => s.edges)
  const getGraph = useStore(s => s.getGraph)

  useEffect(() => {
    if (!nodeId) return

    const edge = handle
      ? edges.find(e => e.target === nodeId && e.targetHandle === handle)
      : edges.find(e => e.target === nodeId)

    if (!edge) { setColumns([]); return }

    setLoading(true)
    apiClient
      .post('/api/preview', { graph: getGraph(), node_id: edge.source })
      .then(r => setColumns(r.data.columns || []))
      .catch(() => setColumns([]))
      .finally(() => setLoading(false))
  }, [nodeId, edges.length, handle])

  return { columns, loading }
}

/**
 * Columns produced by the RIGHT / secondary upstream node of nodeId.
 * Mirrors the executor's logic: prefer edge with targetHandle="right",
 * fall back to the last incoming edge (which is how two edges on the
 * same handle behave when the second handle isn't yet visible).
 */
export function useRightUpstreamColumns(nodeId) {
  const [columns, setColumns] = useState([])
  const [loading, setLoading] = useState(false)

  const edges    = useStore(s => s.edges)
  const getGraph = useStore(s => s.getGraph)

  useEffect(() => {
    if (!nodeId) return
    const inEdges = edges.filter(e => e.target === nodeId)
    if (inEdges.length < 2) { setColumns([]); return }

    // Same resolution as executor.py
    const rightEdge =
      inEdges.find(e => e.targetHandle === 'right') ?? inEdges[inEdges.length - 1]

    setLoading(true)
    apiClient
      .post('/api/preview', { graph: getGraph(), node_id: rightEdge.source })
      .then(r => setColumns(r.data.columns || []))
      .catch(() => setColumns([]))
      .finally(() => setLoading(false))
  }, [nodeId, edges.length])

  return { columns, loading }
}
