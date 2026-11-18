export const API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

export function apiUrl(path) {
  if (!API_BASE_URL) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function wsUrl(path) {
  const explicit = String(import.meta.env.VITE_WS_BASE_URL ?? '').replace(/\/+$/, '')
  if (explicit) return `${explicit}${path.startsWith('/') ? path : `/${path}`}`
  if (API_BASE_URL) {
    const url = new URL(API_BASE_URL)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${url.toString().replace(/\/+$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path.startsWith('/') ? path : `/${path}`}`
}
