import { useEffect, useState } from 'react'
import {
  Boxes, CalendarClock, PlayCircle, Gauge, AlertTriangle, Clock, Database,
} from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import PageHeader from '../components/layout/PageHeader'
import GlassCard from '../components/common/GlassCard'
import LoadingState from '../components/common/LoadingState'
import ErrorState from '../components/common/ErrorState'
import KpiCard from '../components/dashboard/KpiCard'
import ThroughputChart from '../components/dashboard/ThroughputChart'
import PipelineStatusChart from '../components/dashboard/PipelineStatusChart'
import RecentExecutions from '../components/dashboard/RecentExecutions'
import ActivePipelineTable from '../components/dashboard/ActivePipelineTable'
import { useAuth } from '../hooks/useAuth'
import * as dashboardApi from '../services/dashboardApi'
import * as pipelineApi from '../services/pipelineApi'
import * as schedulerApi from '../services/schedulerApi'
import { ApiError } from '../services/apiClient'
import { formatDuration, formatNumber } from '../utils/format'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const [summary, setSummary] = useState(null)
  const [activePipelines, setActivePipelines] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = async () => {
    setLoading(true)
    setError('')
    try {
      const [summaryData, pipelines, schedules] = await Promise.all([
        dashboardApi.getDashboardSummary(),
        pipelineApi.listPipelines(),
        schedulerApi.listAllSchedules().catch(() => []),
      ])
      setSummary(summaryData)

      const nextRunBySlug = new Map()
      schedules.filter(s => s.status === 'active' && s.next_run_at).forEach(s => {
        const existing = nextRunBySlug.get(s.pipeline_slug)
        if (!existing || s.next_run_at < existing) nextRunBySlug.set(s.pipeline_slug, s.next_run_at)
      })
      const active = pipelines
        .filter(p => nextRunBySlug.has(p.name))
        .map(p => ({ ...p, nextRun: nextRunBySlug.get(p.name) }))
        .sort((a, b) => new Date(a.nextRun) - new Date(b.nextRun))
        .slice(0, 6)
      setActivePipelines(active)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  return (
    <AppShell user={user} onLogout={logout}>
      <div className="mx-auto max-w-5xl px-6 pt-24 sm:px-10">
        <PageHeader eyebrow="Overview" title="Dashboard" description="Live status across every pipeline you can see." />

        {loading ? (
          <LoadingState label="Loading dashboard" rows={4} />
        ) : error ? (
          <ErrorState description={error} onRetry={refresh} />
        ) : (
          <div className="space-y-5">
            {summary.failed_jobs > 0 && (
              <div className="flex items-center gap-2.5 rounded-xl border border-red-500/25 bg-red-500/[0.06] px-4 py-3 text-sm text-red-300">
                <AlertTriangle size={15} aria-hidden="true" className="shrink-0" />
                {summary.failed_jobs} run{summary.failed_jobs === 1 ? '' : 's'} failed in the last 24 hours.
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <KpiCard icon={Boxes} label="Total pipelines" value={formatNumber(summary.total_pipelines)} />
              <KpiCard icon={CalendarClock} label="Active schedules" value={formatNumber(summary.active_pipelines)} tone="accent" />
              <KpiCard icon={PlayCircle} label="Runs today" value={formatNumber(summary.runs_today)} />
              <KpiCard icon={Gauge} label="Success rate" value={`${summary.success_rate}%`} tone={summary.success_rate >= 90 ? 'success' : summary.success_rate === 0 ? 'default' : 'error'} />
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <KpiCard icon={PlayCircle} label="Running now" value={formatNumber(summary.running_jobs)} tone="accent" />
              <KpiCard icon={AlertTriangle} label="Failed (24h)" value={formatNumber(summary.failed_jobs)} tone={summary.failed_jobs ? 'error' : 'default'} />
              <KpiCard icon={Clock} label="Avg duration" value={formatDuration(summary.average_duration_seconds)} />
              <KpiCard icon={Database} label="Rows written today" value={formatNumber(summary.records_processed_today)} />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <GlassCard className="p-5 lg:col-span-2">
                <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-white/50">Executions · last 14 days</h2>
                <ThroughputChart series={summary.execution_series} />
              </GlassCard>
              <GlassCard className="p-5">
                <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-white/50">Status breakdown · 30d</h2>
                <PipelineStatusChart breakdown={summary.status_breakdown} />
              </GlassCard>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <GlassCard className="p-5">
                <h2 className="mb-1 text-xs font-bold uppercase tracking-wider text-white/50">Recent executions</h2>
                <RecentExecutions runs={summary.recent_runs} />
              </GlassCard>
              <GlassCard className="p-5">
                <h2 className="mb-1 text-xs font-bold uppercase tracking-wider text-white/50">Upcoming active pipelines</h2>
                <ActivePipelineTable pipelines={activePipelines} />
              </GlassCard>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
