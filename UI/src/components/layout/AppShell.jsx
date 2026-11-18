import { useState } from 'react'
import { apiClient } from '../../services/apiClient'
import { LogOut } from 'lucide-react'
import BackgroundGrid from './BackgroundGrid'
import AmbientGlow from './AmbientGlow'
import BottomDock from './BottomDock'

function UserBadge({ user, onLogout }) {
  const initial = (user.display_name || user.login_id || '?').charAt(0).toUpperCase()
  return (
    <div className="void-glass flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-2">
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/25 text-xs font-bold text-accent-light"
        aria-hidden="true"
      >
        {initial}
      </div>
      <div className="hidden sm:block leading-tight">
        <p className="text-xs font-semibold text-white">{user.display_name || user.login_id}</p>
        <p className="text-[10px] uppercase tracking-wide text-white/40">{user.role}</p>
      </div>
      <button
        type="button"
        onClick={onLogout}
        title="Log out"
        aria-label="Log out"
        className="void-focus ml-1 flex h-7 w-7 items-center justify-center rounded-full text-white/50 transition-colors hover:bg-white/10 hover:text-white"
      >
        <LogOut size={14} />
      </button>
    </div>
  )
}

export default function AppShell({ user, onLogout, children, scroll = true, dock = true, contentClassName = '' }) {
  const [sampleStatus, setSampleStatus] = useState('')
  const [sampleBusy, setSampleBusy] = useState(false)
  return (
    <div className="relative min-h-screen w-full bg-void-bg text-white">
      <BackgroundGrid />
      {import.meta.env.VITE_PUBLIC_DEMO === 'true' && <div className="relative z-20 flex flex-wrap items-center gap-3 border-b border-white/10 bg-black/60 px-5 py-2 text-xs text-white/60"><span>Shared synthetic sandbox · schedules run while the free service is awake</span><button disabled={sampleBusy} className="void-focus rounded border border-white/20 px-2 py-1 text-emerald-300 disabled:opacity-50" onClick={async () => { setSampleBusy(true); try { await apiClient.post('/api/demo/run-schedule/1'); setSampleStatus('Job queued. Open Runtime Logs to see the result.'); } catch (e) { setSampleStatus(e.message); } finally { setSampleBusy(false); } }}>{sampleBusy ? 'Queuing…' : 'Run sample scheduled job'}</button><span role="status">{sampleStatus}</span></div>}
      <AmbientGlow position="top" size={760} />
      <AmbientGlow position="bottom" size={560} className="opacity-50" />

      {user && (
        <div className="fixed top-5 right-5 z-40">
          <UserBadge user={user} onLogout={onLogout} />
        </div>
      )}

      <div
        className={`relative z-10 ${scroll ? 'min-h-screen overflow-y-auto' : 'h-screen overflow-hidden'} ${dock ? 'pb-24' : ''} ${contentClassName}`}
      >
        {children}
      </div>

      {dock && <BottomDock />}
    </div>
  )
}
