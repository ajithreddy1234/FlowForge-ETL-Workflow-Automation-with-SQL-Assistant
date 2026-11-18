import { Globe2, ShieldCheck, UserCircle } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import PageHeader from '../components/layout/PageHeader'
import GlassCard from '../components/common/GlassCard'
import { useAuth } from '../hooks/useAuth'

const APP_TIMEZONE = import.meta.env.VITE_APP_TIMEZONE || 'Not set'

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 border-b border-white/[0.06] py-3.5 last:border-b-0">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-white/50">
        <Icon size={15} aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-white/45">{label}</p>
        <p className="truncate text-sm font-medium text-white">{value}</p>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { user, logout } = useAuth()

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mx-auto max-w-2xl px-6 pt-24 sm:px-10">
        <PageHeader eyebrow="Settings" title="Account & environment" description="Session and workspace configuration for this deployment." />

        <GlassCard className="p-5">
          <Row icon={UserCircle} label="Signed in as" value={`${user?.display_name || user?.login_id} (${user?.login_id})`} />
          <Row icon={ShieldCheck} label="Role" value={user?.role === 'admin' ? 'Administrator — full pipeline management' : 'User — playground, own schedules'} />
          <Row icon={Globe2} label="Schedule timezone" value={APP_TIMEZONE} />
        </GlassCard>

        <p className="mt-4 text-xs text-white/35">
          Database credentials, Google service account, and CORS settings are configured
          by an administrator via the backend environment and are not editable here.
        </p>
      </div>
    </AppShell>
  )
}
