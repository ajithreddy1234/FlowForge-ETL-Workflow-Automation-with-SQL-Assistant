import { getAuthToken } from '../auth'
import { wsUrl } from '../apiConfig'

/**
 * Runs a pipeline graph over the backend's /ws/run WebSocket and streams
 * per-node progress. Centralizes the wire protocol so components never talk
 * to the socket directly.
 */
export function runPipeline(graph, { onProgress, onComplete, onError, onAuthRequired } = {}) {
  const token = getAuthToken()
  if (!token) {
    onAuthRequired?.()
    return { cancel() {} }
  }

  let ws
  let opened = false
  const errors = []

  try {
    ws = new WebSocket(wsUrl('/ws/run'))
  } catch (err) {
    onError?.([{ message: `Could not open WebSocket: ${err.message}` }])
    return { cancel() {} }
  }

  ws.onopen = () => {
    opened = true
    ws.send(JSON.stringify({ token, graph }))
  }

  ws.onmessage = (event) => {
    let msg
    try {
      msg = JSON.parse(event.data)
    } catch {
      return
    }
    if (msg.type === 'progress') {
      onProgress?.(msg)
      if (msg.status === 'error' && msg.error) {
        errors.push({ nodeId: msg.node_id, message: msg.error })
      }
    } else if (msg.type === 'error') {
      if (['Login required', 'Invalid session', 'Session expired', 'Inactive user'].includes(msg.message)) {
        onAuthRequired?.()
        return
      }
      errors.push({ message: msg.message })
      onError?.(errors)
    } else if (msg.type === 'complete') {
      onComplete?.(errors)
    }
  }

  ws.onerror = () => {
    if (!opened) {
      errors.push({
        message: 'WebSocket connection failed — cannot reach the pipeline server. Make sure the API is running.',
      })
      onError?.(errors)
    }
  }

  ws.onclose = (event) => {
    if (!opened && errors.length === 0) {
      errors.push({
        message: `Connection closed before pipeline started (code ${event.code}). The API server may not be running.`,
      })
      onError?.(errors)
    }
  }

  return {
    cancel() {
      try { ws.close() } catch { /* already closed */ }
    },
  }
}
