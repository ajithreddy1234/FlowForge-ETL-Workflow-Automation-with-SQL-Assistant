import axios from 'axios'
import { API_BASE_URL } from '../apiConfig'
import { getAuthToken, clearAuthToken } from '../auth'

export class ApiError extends Error {
  constructor(message, { status = null, code = null, detail = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 20000,
})

apiClient.interceptors.request.use(config => {
  const token = getAuthToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.debug(`[api] ${config.method?.toUpperCase()} ${config.url}`)
  }
  return config
})

apiClient.interceptors.response.use(
  res => res,
  err => {
    if (err.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError(
        'Request is taking too long. Check that the API server is running.',
        { code: 'timeout' },
      ))
    }
    if (!err.response) {
      return Promise.reject(new ApiError(
        'Cannot reach the API server. Check that the backend is running.',
        { code: 'network' },
      ))
    }
    const status = err.response.status
    const data = err.response.data
    const detail = typeof data === 'object' && data !== null ? data.detail : data
    if (status === 401) clearAuthToken()
    return Promise.reject(new ApiError(
      (typeof detail === 'string' && detail) || `Request failed with status ${status}`,
      { status, detail },
    ))
  },
)

export function unwrap(promise) {
  return promise.then(res => res.data)
}
