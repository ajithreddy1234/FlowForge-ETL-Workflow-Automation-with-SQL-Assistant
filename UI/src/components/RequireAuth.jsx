import { Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import LoginModal from './LoginModal'

export default function RequireAuth() {
  const { user, authChecked } = useAuth()
  const navigate = useNavigate()

  if (!authChecked) {
    return <div className="min-h-screen bg-void-bg" />
  }

  if (!user) {
    return (
      <LoginModal
        dismissible={false}
        onSuccess={() => { /* Outlet re-renders once `user` is set */ }}
        onClose={() => navigate('/', { replace: true })}
      />
    )
  }

  return <Outlet />
}
