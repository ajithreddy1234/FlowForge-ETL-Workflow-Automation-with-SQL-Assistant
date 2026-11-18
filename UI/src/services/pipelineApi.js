import { apiClient, unwrap } from './apiClient'

export function listPipelines() {
  return unwrap(apiClient.get('/api/pipelines'))
}

export function getPipeline(name) {
  return unwrap(apiClient.get(`/api/pipelines/${encodeURIComponent(name)}`))
}

export function createPipeline(indexFlowPayload) {
  return unwrap(apiClient.post('/api/pipelines', indexFlowPayload))
}

export function updatePipeline(name, indexFlowPayload) {
  return unwrap(apiClient.put(`/api/pipelines/${encodeURIComponent(name)}`, indexFlowPayload))
}

export function renamePipeline(name, newName) {
  return unwrap(apiClient.patch(`/api/pipelines/${encodeURIComponent(name)}`, { report_name: newName }))
}

export function deletePipeline(name) {
  return unwrap(apiClient.delete(`/api/pipelines/${encodeURIComponent(name)}`))
}
