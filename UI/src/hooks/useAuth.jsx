import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import * as authApi from '../services/authApi'
import { clearAuthToken, getAuthToken, setAuthToken } from '../auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    const token = getAuthToken()
    if (!token) {
      setAuthChecked(true)
      return
    }
    authApi.me()
      .then(setUser)
      .catch(() => {
        clearAuthToken()
        setUser(null)
      })
      .finally(() => setAuthChecked(true))
  }, [])

  const login = useCallback(async (loginId, password) => {
    const res = await authApi.login(loginId, password)
    setAuthToken(res.token)
    setUser(res.user)
    return res.user
  }, [])

  const demoLogin = useCallback(async () => {
    const res = await authApi.demoSession()
    setAuthToken(res.token)
    setUser(res.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Local logout should still clear the session even if the request fails.
    }
    clearAuthToken()
    setUser(null)
  }, [])

  const requireLogin = useCallback(() => {
    clearAuthToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, authChecked, login, demoLogin, logout, requireLogin }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
