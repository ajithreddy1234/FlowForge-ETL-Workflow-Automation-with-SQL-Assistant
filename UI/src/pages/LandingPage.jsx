import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Waypoints, Database, Wand2, Sheet, CalendarClock, ActivitySquare,
  ArrowRight, ShieldCheck,
} from 'lucide-react'
import BackgroundGrid from '../components/layout/BackgroundGrid'
import AmbientGlow from '../components/layout/AmbientGlow'
import GlassCard from '../components/common/GlassCard'
import LoginModal from '../components/LoginModal'
import { useAuth } from '../hooks/useAuth'

const FEATURES = [
  {
    icon: Waypoints,
    title: 'Visual pipeline canvas',
    description: 'Wire Credential, Extract, Transform, and Sink nodes on a drag-and-drop graph — no manual execution order to manage.',
  },
  {
    icon: Database,
    title: 'A ready-to-query orders source',
    description: 'Explore 240 synthetic orders with read-only SQL and table previews. External warehouse connectors are available in the source code for private deployments.',
  },
  {
    icon: Wand2,
    title: '20 structured transforms',
    description: 'Filter, group, pivot, rank, and reshape data with operations backed by the pandas transform engine.',
  },
  {
    icon: Sheet,
    title: 'Real CSV output',
    description: 'Write transformed results on the server and download the latest CSV. Google Sheets output is supported in private deployments.',
  },
  {
    icon: CalendarClock,
    title: 'Scheduled execution',
    description: 'Run pipelines on a cron or one-off schedule, with per-run history, retries, and stale-run recovery.',
  },
  {
    icon: ActivitySquare,
    title: 'Observable runs',
    description: 'Interactive runs stream per-node progress. Scheduled runs record status, duration, output rows, and errors.',
  },
]

function FlowDiagram() {
  return (
    <div className="relative mx-auto mt-14 flex max-w-2xl items-center justify-between gap-2" aria-hidden="true">
      {['Source', 'Transform', 'Sheet'].map((label, i) => (
        <div key={label} className="flex items-center gap-2 flex-1">
          <div
            className="void-glass flex flex-1 flex-col items-center gap-1.5 rounded-2xl px-4 py-5 shadow-glow-accent-sm animate-float"
            style={{ animationDelay: `${i * 0.4}s` }}
          >
            <span className="font-mono text-[10px] uppercase tracking-wider text-accent-light">{label}</span>
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
          </div>
          {i < 2 && (
            <svg width="40" height="12" viewBox="0 0 40 12" className="shrink-0 text-accent/60">
              <line x1="0" y1="6" x2="36" y2="6" stroke="currentColor" strokeWidth="2" strokeDasharray="5 5" className="animate-dash-flow" />
              <path d="M32 1 L38 6 L32 11" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}

export default function LandingPage() {
  const { user, demoLogin } = useAuth()
  const [demoBusy, setDemoBusy] = useState(false)
  const [demoError, setDemoError] = useState('')
  const navigate = useNavigate()
  const [loginOpen, setLoginOpen] = useState(false)
  const [pendingPath, setPendingPath] = useState('/workspaces')

  const goAuthenticated = async (path) => {
    if (import.meta.env.VITE_PUBLIC_DEMO === 'true' && !user) {
      setDemoBusy(true)
      setDemoError('')
      try { await demoLogin(); navigate(path === '/pipelines/new' ? '/pipelines/regional_revenue' : path) }
      catch (error) { setDemoError(error.message || 'Could not open the sandbox. Please retry.'); }
      finally { setDemoBusy(false) }
      return
    }
    if (user) {
      navigate(path)
      return
    }
    setPendingPath(path)
    setLoginOpen(true)
  }

  return (
    <div className="relative min-h-screen overflow-x-clip bg-void-bg text-white">
      <BackgroundGrid />
      <AmbientGlow position="top" size={820} />

      {/* Floating nav */}
      <header className="fixed inset-x-0 top-4 z-40 flex justify-center px-4">
        <nav className="void-glass flex w-full max-w-3xl items-center justify-between rounded-full px-5 py-2.5">
          <a href="#top" className="flex items-center gap-2 font-mono text-sm font-bold tracking-widest">
            <img src="/flowforge-mark.svg" width="27" height="27" alt="" />
            FLOWFORGE
          </a>
          <div className="hidden items-center gap-6 text-sm text-white/60 sm:flex">
            <a href="#product" className="void-focus rounded transition-colors hover:text-white">Product</a>
            <a href="#how-it-works" className="void-focus rounded transition-colors hover:text-white">Documentation</a>
          </div>
          <button
            type="button"
            onClick={() => goAuthenticated('/workspaces')}
            className="void-focus rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent-hover"
          >
            {demoBusy ? 'Opening…' : 'Open sandbox'}
          </button>
        </nav>
      </header>

      {/* Hero */}
      <main id="top">
        <section className="relative mx-auto max-w-4xl px-6 pb-24 pt-40 text-center sm:pt-48">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-accent-light">
            Visual pipelines · Scheduled execution · Observable runs
          </p>
          <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            Build, automate and monitor
            <br className="hidden sm:block" /> data pipelines visually.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-base text-white/55 sm:text-lg">
            Connect databases, transform records, and load results into destinations
            without manually wiring every execution.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => goAuthenticated('/pipelines/new')}
              className="void-focus inline-flex items-center gap-2 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white shadow-glow-accent transition-colors hover:bg-accent-hover"
            >
              {import.meta.env.VITE_PUBLIC_DEMO === 'true' ? 'Run the sample pipeline' : 'Build a pipeline'}
              <ArrowRight size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => goAuthenticated('/dashboard')}
              className="void-focus inline-flex items-center gap-2 rounded-xl border border-white/12 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
            >
              Open Dashboard
            </button>
          </div>

          {demoError && <p role="alert" className="mt-4 text-sm text-red-300">{demoError}</p>}
          {import.meta.env.VITE_PUBLIC_DEMO === 'true' ? <p className="mx-auto mt-6 max-w-xl text-xs leading-relaxed text-white/50">Public sandbox · synthetic orders only. Run SQL, edit transforms, save a copy, download CSV output, and schedule a job. Shared demonstration history resets when the free service restarts. Scheduled jobs run while the service is awake.</p> : <p className="mx-auto mt-6 max-w-xl text-xs leading-relaxed text-white/50">Sign in to connect PostgreSQL, MySQL or Redshift sources, generate SQL from your catalog with the AI assistant, and load results into Google Sheets on a schedule.</p>}
          <FlowDiagram />
        </section>

        {/* Feature grid */}
        <section id="product" className="mx-auto max-w-5xl px-6 pb-24">
          <h2 className="mb-8 text-center text-xs font-semibold uppercase tracking-[0.3em] text-white/40">
            What's inside
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <GlassCard key={title} hover className="p-5">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent-light">
                  <Icon size={17} aria-hidden="true" />
                </div>
                <h3 className="text-sm font-bold text-white">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-white/50">{description}</p>
              </GlassCard>
            ))}
          </div>
        </section>

        {/* Roles / how it works */}
        <section id="how-it-works" className="mx-auto max-w-3xl px-6 pb-24">
          <GlassCard className="p-6 sm:p-8">
            <div className="flex items-center gap-2.5 mb-4">
              <ShieldCheck size={18} className="text-accent-light" aria-hidden="true" />
              <h2 className="text-sm font-bold text-white">Database-backed access</h2>
            </div>
            <p className="text-sm leading-relaxed text-white/55">
              This public deployment opens a limited demo session against synthetic data. In private deployments, admins can
              create, edit, rename, delete and schedule any saved pipeline; other users can
              build in the playground, save their own copies, run pipelines, and manage the
              schedules they created. Saved credential passwords are encrypted at rest.
            </p>
          </GlassCard>
        </section>

        {/* Final CTA */}
        <section className="mx-auto max-w-2xl px-6 pb-28 text-center">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">
            Ready to build your first pipeline?
          </h2>
          <div className="mt-6">
            <button
              type="button"
              onClick={() => goAuthenticated('/workspaces')}
              className="void-focus inline-flex items-center gap-2 rounded-xl bg-accent px-7 py-3 text-sm font-semibold text-white shadow-glow-accent transition-colors hover:bg-accent-hover"
            >
              Launch Console
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.06] px-6 py-8 text-center text-xs text-white/35">
        FlowForge — FastAPI + React
      </footer>

      {loginOpen && (
        <LoginModal
          onClose={() => setLoginOpen(false)}
          onSuccess={() => {
            setLoginOpen(false)
            navigate(pendingPath)
          }}
        />
      )}
    </div>
  )
}
