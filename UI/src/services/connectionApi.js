import { apiClient, unwrap } from './apiClient'

export function checkDbConnection(payload) {
  return unwrap(apiClient.post('/api/db/check-connection', payload))
}

export function previewNode(graph, nodeId) {
  return unwrap(apiClient.post('/api/preview', { graph, node_id: nodeId }))
}

export function listConnections() {
  return unwrap(apiClient.get('/api/connections'))
}

export function createConnection(payload) {
  return unwrap(apiClient.post('/api/connections', payload))
}

export function checkSavedConnection(connectionId) {
  return unwrap(apiClient.post(`/api/connections/${connectionId}/check`))
}

export function syncCatalog(connectionId) {
  return unwrap(apiClient.post(
    `/api/connections/${connectionId}/catalog/sync`,
    undefined,
    { timeout: 180000 },
  ))
}

export function getCatalog(connectionId) {
  return unwrap(apiClient.get(`/api/connections/${connectionId}/catalog`))
}
