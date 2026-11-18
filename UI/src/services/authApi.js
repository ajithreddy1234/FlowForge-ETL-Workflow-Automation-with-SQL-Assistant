import { apiClient, unwrap } from './apiClient'

export function login(loginId, password) {
  return unwrap(apiClient.post('/api/auth/login', { login_id: loginId, password }))
}

export function logout() {
  return unwrap(apiClient.post('/api/auth/logout'))
}

export function me() {
  return unwrap(apiClient.get('/api/auth/me')).then(res => res.user)
}

export function demoSession() { return unwrap(apiClient.post("/api/demo/session")) }
