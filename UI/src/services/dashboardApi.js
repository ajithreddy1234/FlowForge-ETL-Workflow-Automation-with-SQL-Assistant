import { apiClient, unwrap } from './apiClient'

export function getDashboardSummary() {
  return unwrap(apiClient.get('/api/dashboard/summary'))
}
