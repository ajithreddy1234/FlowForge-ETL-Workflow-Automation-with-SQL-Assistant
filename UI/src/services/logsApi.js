import { apiClient, unwrap } from './apiClient'

export function listRuntimeLogs({ status, pipeline, search, limit } = {}) {
  const params = {}
  if (status && status !== 'all') params.status = status
  if (pipeline) params.pipeline = pipeline
  if (search) params.search = search
  if (limit) params.limit = limit
  return unwrap(apiClient.get('/api/logs', { params }))
}

export function getRuntimeLog(runId) {
  return unwrap(apiClient.get(`/api/logs/${runId}`))
}
