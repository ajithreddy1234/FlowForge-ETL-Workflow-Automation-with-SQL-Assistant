import { useEffect, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import LoginModal from './LoginModal'

export default function RequireAuth() {
  const { user, authChecked, demoLogin } = useAuth()
  const navigate = useNavigate()
  const demo = import.meta.env.VITE_PUBLIC_DEMO === 'true'
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!demo || !authChecked || user) return
    let active = true
    setError('')
    demoLogin().catch(failure => { if (active) setError(failure.message || 'Could not open the sandbox.') })
    return () => { active = false }
  }, [demo, authChecked, user, demoLogin, attempt])

  if (!authChecked || (demo && !user)) {
    return <div className="flex min-h-screen items-center justify-center bg-void-bg p-6 text-white"><div className="max-w-md text-center"><p role={error ? 'alert' : 'status'} className="text-sm text-white/60">{error || 'Opening your synthetic-data sandbox…'}</p>{error && <div className="mt-4 flex justify-center gap-4"><button className="void-focus rounded-lg bg-accent px-4 py-2 text-sm" onClick={() => setAttempt(value => value + 1)}>Try again</button><a className="void-focus py-2 text-sm underline" href="/">Back to FlowForge</a></div>}</div></div>
  }

  if (!user) {
    return <LoginModal dismissible={false} onSuccess={() => {}} onClose={() => navigate('/', { replace: true })} />
  }
  return <Outlet />
}
