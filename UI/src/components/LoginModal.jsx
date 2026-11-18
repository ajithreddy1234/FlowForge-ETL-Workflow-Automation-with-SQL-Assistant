import { useEffect, useRef, useState } from 'react'
import { Eye, EyeOff, X, Waypoints } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export default function LoginModal({ onClose, onSuccess, dismissible = true }) {
  const { login } = useAuth()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const dialogRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && dismissible) onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, dismissible])

  const submit = async (e) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError('')
    try {
      const user = await login(loginId, password)
      onSuccess?.(user)
    } catch (err) {
      setError(err.message || 'Invalid login ID or password')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={e => { if (dismissible && e.target === e.currentTarget) onClose?.() }}
    >
      <form
        ref={dialogRef}
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
        className="void-glass w-full max-w-sm rounded-2xl p-6 shadow-[0_24px_64px_rgba(0,0,0,0.55)] animate-fade-up"
      >
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/20 text-accent-light">
              <Waypoints size={18} aria-hidden="true" />
            </div>
            <div>
              <h2 id="login-title" className="text-base font-bold text-white">Sign in</h2>
              <p className="text-xs text-white/45">Use your assigned credentials</p>
            </div>
          </div>
          {dismissible && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close login dialog"
              className="void-focus rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <label htmlFor="login-id" className="mb-1.5 block text-xs font-semibold text-white/60">User ID</label>
        <input
          id="login-id"
          ref={inputRef}
          value={loginId}
          onChange={e => setLoginId(e.target.value)}
          autoComplete="username"
          className="void-focus mb-3.5 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-white outline-none placeholder:text-white/30 focus:border-accent/50"
        />

        <label htmlFor="login-password" className="mb-1.5 block text-xs font-semibold text-white/60">Password</label>
        <div className="relative">
          <input
            id="login-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="current-password"
            className="void-focus w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5 pr-10 text-sm text-white outline-none placeholder:text-white/30 focus:border-accent/50"
          />
          <button
            type="button"
            onClick={() => setShowPassword(v => !v)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="void-focus absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-white/40 hover:text-white"
          >
            {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>

        {error && (
          <p role="alert" className="mt-3 text-xs font-medium text-red-400">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="void-focus mt-5 w-full rounded-lg bg-accent px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
