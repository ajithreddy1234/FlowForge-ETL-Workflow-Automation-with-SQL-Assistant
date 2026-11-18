import { apiClient, unwrap } from './apiClient'

export function listAllSchedules() {
  return unwrap(apiClient.get('/api/schedules'))
}

export function listPipelineSchedules(pipelineSlug) {
  return unwrap(apiClient.get(`/api/pipelines/${encodeURIComponent(pipelineSlug)}/schedules`))
}

export function createPipelineSchedules(pipelineSlug, rules) {
  return unwrap(apiClient.post(`/api/pipelines/${encodeURIComponent(pipelineSlug)}/schedules`, { rules }))
}

export function pauseSchedule(scheduleId) {
  return unwrap(apiClient.post(`/api/schedules/${scheduleId}/pause`))
}

export function startSchedule(scheduleId) {
  return unwrap(apiClient.post(`/api/schedules/${scheduleId}/start`))
}

export function deleteSchedule(scheduleId) {
  return unwrap(apiClient.delete(`/api/schedules/${scheduleId}`))
}

export function getScheduleLogs(scheduleId) {
  return unwrap(apiClient.get(`/api/schedules/${scheduleId}/logs`))
}

export function listUpcomingSchedules() {
  return unwrap(apiClient.get('/api/schedules/upcoming'))
}

export function listPipelineUpcomingSchedules(pipelineSlug) {
  return unwrap(apiClient.get(`/api/pipelines/${encodeURIComponent(pipelineSlug)}/schedules/upcoming`))
}
