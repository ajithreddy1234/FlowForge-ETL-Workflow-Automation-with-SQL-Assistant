import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, Boxes, ScrollText, Waypoints, ArrowUpRight } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import GlassCard from '../components/common/GlassCard'
import { useAuth } from '../hooks/useAuth'

function WorkspaceCard({ icon: Icon, title, description, to, featured = false, delay = 0 }) {
  const navigate = useNavigate()
  return (
    <GlassCard
      as="button"
      hover
      onClick={() => navigate(to)}
      className={`group relative flex flex-col justify-between p-6 text-left animate-fade-up ${
        featured ? 'shadow-glow-accent-sm border-accent/30' : ''
      }`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div>
        <div
          className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${
            featured ? 'bg-accent/25 text-accent-light' : 'bg-white/[0.06] text-white/60'
          }`}
        >
          <Icon size={20} aria-hidden="true" />
        </div>
        <h2 className="text-lg font-bold text-white">{title}</h2>
        <p className="mt-1.5 text-sm text-white/50">{description}</p>
      </div>
      <div className="mt-6 flex items-center gap-1.5 text-xs font-semibold text-white/40 transition-colors group-hover:text-accent-light">
        Open
        <ArrowUpRight size={13} aria-hidden="true" />
      </div>
    </GlassCard>
  )
}

export default function WorkspacePage() {
  const { user, logout } = useAuth()

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mx-auto max-w-5xl px-6 pt-24 sm:pt-32">
        <div className="text-center animate-fade-up">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent-light">
            {user?.display_name || user?.login_id}
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Select workspace
          </h1>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <WorkspaceCard
              icon={Waypoints}
              title="Visual Editor"
              description="Build a new pipeline on the drag-and-drop canvas — connect a credential, extract, transform, and destination."
              to="/pipelines/new"
              featured
            />
          </div>
          <WorkspaceCard
            icon={LayoutDashboard}
            title="Dashboard"
            description="Live KPIs, run history, and status breakdown across every pipeline you can see."
            to="/dashboard"
            delay={80}
          />
          <WorkspaceCard
            icon={Boxes}
            title="Pipelines"
            description="Browse, search, schedule, and manage every saved pipeline."
            to="/pipelines"
            delay={140}
          />
          <div className="sm:col-span-2">
            <WorkspaceCard
              icon={ScrollText}
              title="Runtime Logs"
              description="Inspect scheduled execution history: status, duration, rows written, and errors."
              to="/logs"
              delay={200}
            />
          </div>
        </div>
      </div>
    </AppShell>
  )
}
