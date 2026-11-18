import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, MoreVertical, Edit3, CalendarClock, Copy, Trash2, Pencil, Play, Boxes,
} from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import PageHeader from '../components/layout/PageHeader'
import CommandBar from '../components/layout/CommandBar'
import GlassCard from '../components/common/GlassCard'
import StatusBadge from '../components/common/StatusBadge'
import LoadingState from '../components/common/LoadingState'
import EmptyState from '../components/common/EmptyState'
import ErrorState from '../components/common/ErrorState'
import ConfirmDialog from '../components/common/ConfirmDialog'
import ScheduleModal from '../components/ScheduleModal'
import { useToast } from '../components/common/Toast'
import { useAuth } from '../hooks/useAuth'
import * as pipelineApi from '../services/pipelineApi'
import * as schedulerApi from '../services/schedulerApi'
import { runPipeline } from '../services/executionApi'
import { ApiError } from '../services/apiClient'
import { reportToGraph } from '../reportImporter'
import { formatDateTime } from '../utils/format'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'paused', label: 'Paused' },
  { id: 'failed', label: 'Failed' },
  { id: 'unscheduled', label: 'Unscheduled' },
]

const SORTS = [
  { id: 'updated', label: 'Last updated' },
  { id: 'name', label: 'Name' },
  { id: 'status', label: 'Schedule status' },
]

function scheduleSummary(scheduleRows) {
  const map = new Map()
  scheduleRows.forEach(s => {
    const slug = s.pipeline_slug
    if (!slug) return
    if (!map.has(slug)) map.set(slug, [])
    map.get(slug).push(s)
  })
  const summaries = new Map()
  map.forEach((rows, slug) => {
    const active = rows.filter(r => r.status === 'active')
    const nextRun = active
      .map(r => r.next_run_at)
      .filter(Boolean)
      .sort()[0]
    const mostRecent = [...rows].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))[0]
    summaries.set(slug, {
      count: rows.length,
      activeCount: active.length,
      nextRun,
      lastRun: mostRecent?.last_run_at || null,
      lastStatus: mostRecent?.last_status || null,
      status: active.length > 0 ? 'active' : rows.length > 0 ? 'paused' : null,
    })
  })
  return summaries
}

export default function PipelineListPage() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'

  const [pipelines, setPipelines] = useState([])
  const [schedulesBySlug, setSchedulesBySlug] = useState(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('updated')
  const [openMenu, setOpenMenu] = useState(null)
  const [renameTarget, setRenameTarget] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [scheduleTarget, setScheduleTarget] = useState(null)
  const [runningSlug, setRunningSlug] = useState(null)

  const refresh = async () => {
    setLoading(true)
    setError('')
    try {
      const [pipelineRows, scheduleRows] = await Promise.all([
        pipelineApi.listPipelines(),
        schedulerApi.listAllSchedules().catch(() => []),
      ])
      setPipelines(pipelineRows)
      setSchedulesBySlug(scheduleSummary(scheduleRows))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load pipelines')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  useEffect(() => {
    if (!openMenu) return
    const closeOnOutside = () => setOpenMenu(null)
    const closeOnEscape = (e) => { if (e.key === 'Escape') setOpenMenu(null) }
    document.addEventListener('pointerdown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [openMenu])

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    let list = pipelines.map(p => ({ ...p, schedule: schedulesBySlug.get(p.name) || null }))

    if (q) {
      list = list.filter(p => [p.pipeline_name, p.created_by, p.created_by_login_id, p.last_edited_by, p.last_edited_by_login_id]
        .some(v => String(v || '').toLowerCase().includes(q)))
    }

    if (filter === 'active') list = list.filter(p => p.schedule?.status === 'active')
    else if (filter === 'paused') list = list.filter(p => p.schedule && p.schedule.status !== 'active')
    else if (filter === 'failed') list = list.filter(p => p.schedule?.lastStatus === 'failed')
    else if (filter === 'unscheduled') list = list.filter(p => !p.schedule)

    list = [...list].sort((a, b) => {
      if (sort === 'name') return a.pipeline_name.localeCompare(b.pipeline_name)
      if (sort === 'status') return (b.schedule?.status === 'active' ? 1 : 0) - (a.schedule?.status === 'active' ? 1 : 0)
      return new Date(b.updated_at) - new Date(a.updated_at)
    })

    return list
  }, [pipelines, schedulesBySlug, search, filter, sort])

  const editPipeline = (slug) => navigate(`/pipelines/${encodeURIComponent(slug)}`)

  const runNow = async (pipeline) => {
    setOpenMenu(null)
    setRunningSlug(pipeline.name)
    try {
      const report = await pipelineApi.getPipeline(pipeline.name)
      const graph = reportToGraph(report)
      await new Promise((resolve, reject) => {
        runPipeline(graph, {
          onComplete: (errors) => (errors.length ? reject(new Error(errors[0].message)) : resolve()),
          onError: (errors) => reject(new Error(errors[0]?.message || 'Run failed')),
          onAuthRequired: () => reject(new Error('Your session expired. Please sign in again.')),
        })
      })
      toast.push(`${pipeline.pipeline_name} ran successfully`, { type: 'success' })
      refresh()
    } catch (err) {
      toast.push(err.message || 'Pipeline run failed', { type: 'error' })
    } finally {
      setRunningSlug(null)
    }
  }

  const duplicatePipeline = async (pipeline) => {
    setOpenMenu(null)
    try {
      const report = await pipelineApi.getPipeline(pipeline.name)
      report.report_name = `${pipeline.pipeline_name} Copy`
      await pipelineApi.createPipeline(report)
      toast.push('Pipeline duplicated', { type: 'success' })
      refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Duplicate failed', { type: 'error' })
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await pipelineApi.deletePipeline(deleteTarget.name)
      toast.push('Pipeline deleted', { type: 'success' })
      setDeleteTarget(null)
      refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Delete failed', { type: 'error' })
    }
  }

  const submitRename = async () => {
    if (!renameTarget || !renameValue.trim()) return
    try {
      await pipelineApi.renamePipeline(renameTarget.name, renameValue.trim())
      toast.push('Pipeline renamed', { type: 'success' })
      setRenameTarget(null)
      refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Rename failed', { type: 'error' })
    }
  }

  const activeCount = pipelines.length
    ? [...schedulesBySlug.values()].filter(s => s.status === 'active').length
    : 0

  return (
    <AppShell user={user} onLogout={logout} scroll dock>
      <div className="mx-auto max-w-5xl px-6 pt-24 sm:px-10">
        <PageHeader
          eyebrow="Pipelines"
          title="Saved pipelines"
          description={`${pipelines.length} pipeline${pipelines.length === 1 ? '' : 's'} · ${activeCount} actively scheduled`}
          actions={(
            <button
              type="button"
              onClick={() => navigate('/pipelines/new')}
              className="void-focus flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover"
            >
              <Plus size={15} aria-hidden="true" />
              New Pipeline
            </button>
          )}
        />

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CommandBar value={search} onChange={setSearch} placeholder="Search pipelines…" className="sm:max-w-xs" />
          <div className="flex flex-wrap items-center gap-1.5">
            {FILTERS.map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={`void-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  filter === f.id ? 'bg-accent/20 text-accent-light' : 'text-white/50 hover:bg-white/5'
                }`}
              >
                {f.label}
              </button>
            ))}
            <select
              value={sort}
              onChange={e => setSort(e.target.value)}
              aria-label="Sort pipelines"
              className="void-focus rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-white/60 outline-none"
            >
              {SORTS.map(s => <option key={s.id} value={s.id}>Sort: {s.label}</option>)}
            </select>
          </div>
        </div>

        {loading ? (
          <LoadingState label="Loading pipelines" rows={4} />
        ) : error ? (
          <ErrorState description={error} onRetry={refresh} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title={pipelines.length === 0 ? 'No saved pipelines yet' : 'No pipelines match your filters'}
            description={pipelines.length === 0 ? 'Build your first pipeline on the visual canvas.' : 'Try a different search term or filter.'}
            action={pipelines.length === 0 && (
              <button type="button" onClick={() => navigate('/pipelines/new')} className="void-focus rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover">
                Build Pipeline
              </button>
            )}
          />
        ) : (
          <div className="space-y-2.5">
            {rows.map(p => (
              <GlassCard key={p.name} hover className="group relative flex flex-wrap items-center gap-4 p-4">
                <button
                  type="button"
                  onClick={() => editPipeline(p.name)}
                  className="void-focus min-w-[180px] flex-1 text-left"
                >
                  <p className="truncate text-sm font-bold text-white">{p.pipeline_name}</p>
                  <p className="mt-0.5 truncate text-xs text-white/40">
                    v{p.version || 1} · {p.nodes} nodes · {p.edges} links · edited by {p.last_edited_by || p.created_by || 'someone'}
                  </p>
                </button>

                <div className="hidden shrink-0 flex-col text-xs text-white/40 sm:flex">
                  <span>Updated</span>
                  <span className="font-mono text-white/60">{formatDateTime(p.updated_at)}</span>
                </div>

                <div className="hidden shrink-0 flex-col text-xs text-white/40 md:flex">
                  <span>Next run</span>
                  <span className="font-mono text-white/60">{p.schedule?.nextRun ? formatDateTime(p.schedule.nextRun) : '—'}</span>
                </div>

                <div className="shrink-0">
                  {p.schedule ? <StatusBadge status={p.schedule.status} /> : <StatusBadge status="idle" />}
                </div>

                <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <button
                    type="button"
                    onClick={() => runNow(p)}
                    disabled={runningSlug === p.name}
                    title="Run now"
                    aria-label={`Run ${p.pipeline_name} now`}
                    className="void-focus rounded-lg border border-white/10 p-2 text-white/60 hover:bg-white/5 disabled:opacity-50"
                  >
                    <Play size={14} className={runningSlug === p.name ? 'animate-pulse' : ''} />
                  </button>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setOpenMenu(openMenu === p.name ? null : p.name)}
                      aria-label={`More actions for ${p.pipeline_name}`}
                      className="void-focus rounded-lg border border-white/10 p-2 text-white/60 hover:bg-white/5"
                    >
                      <MoreVertical size={14} />
                    </button>
                    {openMenu === p.name && (
                      <div className="void-glass absolute right-0 top-10 z-20 w-44 overflow-hidden rounded-xl py-1 text-sm">
                        <MenuItem icon={Edit3} label="Edit" onClick={() => { setOpenMenu(null); editPipeline(p.name) }} />
                        <MenuItem icon={CalendarClock} label="Schedule" onClick={() => { setOpenMenu(null); setScheduleTarget(p) }} />
                        <MenuItem icon={Copy} label="Duplicate" onClick={() => duplicatePipeline(p)} />
                        {isAdmin && (
                          <>
                            <MenuItem icon={Pencil} label="Rename" onClick={() => { setOpenMenu(null); setRenameTarget(p); setRenameValue(p.pipeline_name) }} />
                            <MenuItem icon={Trash2} label="Delete" danger onClick={() => { setOpenMenu(null); setDeleteTarget(p) }} />
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>

      {renameTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm" onMouseDown={e => { if (e.target === e.currentTarget) setRenameTarget(null) }}>
          <div className="void-glass w-full max-w-sm rounded-2xl p-5">
            <h2 className="text-sm font-bold text-white">Rename pipeline</h2>
            <input
              autoFocus
              value={renameValue}
              onChange={e => setRenameValue(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitRename()}
              className="void-focus mt-3 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setRenameTarget(null)} className="void-focus rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/5">Cancel</button>
              <button type="button" onClick={submitRename} className="void-focus rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-hover">Save</button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete "${deleteTarget?.pipeline_name}"?`}
        description="This permanently removes the saved pipeline and its schedules. This cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {scheduleTarget && (
        <ScheduleModal pipeline={scheduleTarget} currentUser={user} onClose={() => setScheduleTarget(null)} />
      )}
    </AppShell>
  )
}

function MenuItem({ icon: Icon, label, onClick, danger = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`void-focus flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-white/5 ${
        danger ? 'text-red-400' : 'text-white/75'
      }`}
    >
      <Icon size={13} aria-hidden="true" />
      {label}
    </button>
  )
}
