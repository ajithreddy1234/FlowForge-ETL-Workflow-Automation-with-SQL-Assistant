import { apiClient, unwrap } from './apiClient'

export function generateSql(connectionId, requirement) {
  return unwrap(apiClient.post('/api/sql-assistant/generate', {
    connection_id: connectionId,
    requirement,
  }, { timeout: 240000 }))
}

export function previewSql(candidateId, limit = 100) {
  return unwrap(apiClient.post(
    `/api/sql-assistant/${candidateId}/preview`,
    { limit },
    { timeout: 320000 },
  ))
}

export function approveSql(candidateId) {
  return unwrap(apiClient.post(`/api/sql-assistant/${candidateId}/approve`))
}
