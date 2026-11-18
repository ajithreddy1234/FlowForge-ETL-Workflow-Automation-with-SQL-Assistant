import { useEffect, useState } from 'react'
import { X, Plus, Trash2, Pause, CirclePlay, ScrollText, CalendarClock } from 'lucide-react'
import * as schedulerApi from '../services/schedulerApi'
import { ApiError } from '../services/apiClient'
import StatusBadge from './common/StatusBadge'
import { useToast } from './common/Toast'
import { formatDateTime } from '../utils/format'
import { newScheduleDraft, buildScheduleRules, formatScheduleWindow } from '../utils/schedule'

function fieldLabel(text) {
  return <span className="text-xs font-semibold text-white/55">{text}</span>
}

export default function ScheduleModal({ pipeline, currentUser, onClose }) {
  const toast = useToast()
  const isAdmin = currentUser?.role === 'admin'
  const [schedules, setSchedules] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [drafts, setDrafts] = useState([newScheduleDraft()])
  const [saving, setSaving] = useState(false)
  const [selectedSchedule, setSelectedSchedule] = useState(null)
  const [logs, setLogs] = useState([])

  const refresh = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const rows = await schedulerApi.listPipelineSchedules(pipeline.name)
      setSchedules(rows)
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Could not load schedules')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [pipeline.name])

  useEffect(() => {
    const onKeyDown = e => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const updateDraft = (id, changes) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, ...changes } : d)))
  const addDraft = () => setDrafts(prev => [...prev, newScheduleDraft()])
  const removeDraft = (id) => setDrafts(prev => (prev.length === 1 ? prev : prev.filter(d => d.id !== id)))
  const addDraftTime = (id) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, times: [...d.times, '09:00'] } : d)))
  const updateDraftTime = (id, i, v) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, times: d.times.map((t, idx) => (idx === i ? v : t)) } : d)))
  const removeDraftTime = (id, i) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, times: d.times.length === 1 ? d.times : d.times.filter((_, idx) => idx !== i) } : d)))
  const addDraftDate = (id) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, dates: [...d.dates, ''] } : d)))
  const updateDraftDate = (id, i, v) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, dates: d.dates.map((dt, idx) => (idx === i ? v : dt)) } : d)))
  const removeDraftDate = (id, i) => setDrafts(prev => prev.map(d => (d.id === id ? { ...d, dates: d.dates.length === 1 ? d.dates : d.dates.filter((_, idx) => idx !== i) } : d)))

  const save = async () => {
    const rules = buildScheduleRules(drafts)
    if (!rules.length) {
      toast.push('Add at least one valid schedule with date/frequency and time', { type: 'error' })
      return
    }
    setSaving(true)
    try {
      await schedulerApi.createPipelineSchedules(pipeline.name, rules)
      toast.push(`${rules.length} schedule${rules.length === 1 ? '' : 's'} saved`, { type: 'success' })
      setDrafts([newScheduleDraft()])
      await refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Save schedule failed', { type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (schedule) => {
    try {
      if (schedule.status === 'active') await schedulerApi.pauseSchedule(schedule.id)
      else await schedulerApi.startSchedule(schedule.id)
      toast.push(schedule.status === 'active' ? 'Schedule paused' : 'Schedule started', { type: 'success' })
      await refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Could not update schedule', { type: 'error' })
    }
  }

  const remove = async (schedule) => {
    try {
      await schedulerApi.deleteSchedule(schedule.id)
      if (selectedSchedule?.id === schedule.id) { setSelectedSchedule(null); setLogs([]) }
      toast.push('Schedule deleted', { type: 'success' })
      await refresh()
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Could not delete schedule', { type: 'error' })
    }
  }

  const viewLogs = async (schedule) => {
    setSelectedSchedule(schedule)
    try {
      setLogs(await schedulerApi.getScheduleLogs(schedule.id))
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : 'Could not load logs', { type: 'error' })
    }
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-start justify-center overflow-y-auto bg-black/70 px-4 py-10 backdrop-blur-sm">
      <div className="void-glass w-full max-w-2xl rounded-2xl shadow-[0_24px_64px_rgba(0,0,0,0.55)] animate-fade-up">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <CalendarClock size={17} className="text-accent-light shrink-0" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-sm font-bold text-white">Schedule: {pipeline.pipeline_name}</h2>
              <p className="text-xs text-white/40">Create and manage run schedules for this pipeline</p>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close schedule dialog" className="void-focus rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white">
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-6 py-5 space-y-5">
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-white/50">New schedules</h3>
              <button type="button" onClick={addDraft} className="void-focus flex items-center gap-1.5 rounded-lg bg-accent/15 px-2.5 py-1.5 text-xs font-semibold text-accent-light hover:bg-accent/25">
                <Plus size={13} />Add rule
              </button>
            </div>

            {drafts.map((draft, idx) => (
              <div key={draft.id} className="void-card rounded-xl p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-white/70">Rule {idx + 1}</p>
                  {drafts.length > 1 && (
                    <button type="button" onClick={() => removeDraft(draft.id)} className="void-focus rounded-md px-2 py-1 text-[11px] text-red-400 hover:bg-red-500/10">Remove</button>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-[160px_1fr]">
                  <label className="space-y-1">
                    {fieldLabel('Frequency')}
                    <select
                      value={draft.frequency}
                      onChange={e => updateDraft(draft.id, { frequency: e.target.value })}
                      className="void-focus w-full rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-2 text-sm text-white outline-none"
                    >
                      <option value="daily">Daily</option>
                      <option value="weekdays">Mon–Fri</option>
                      <option value="custom_dates">Custom date</option>
                    </select>
                  </label>
                  {draft.frequency === 'custom_dates' ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        {fieldLabel('Dates')}
                        <button type="button" onClick={() => addDraftDate(draft.id)} className="void-focus text-[11px] font-semibold text-accent-light">Add date</button>
                      </div>
                      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                        {draft.dates.map((d, i) => (
                          <div key={i} className="flex gap-1.5">
                            <input type="date" value={d} onChange={e => updateDraftDate(draft.id, i, e.target.value)} className="void-focus w-full rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1.5 text-xs text-white outline-none" />
                            <button type="button" onClick={() => removeDraftDate(draft.id, i)} aria-label="Remove date" className="void-focus rounded-lg border border-white/10 px-2 text-white/40 hover:text-red-400">×</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-end pb-0.5 text-xs text-white/40">
                      {draft.frequency === 'daily' ? 'Runs every day' : 'Runs Monday to Friday'}
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    {fieldLabel('Times')}
                    <button type="button" onClick={() => addDraftTime(draft.id)} className="void-focus text-[11px] font-semibold text-accent-light">Add time</button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                    {draft.times.map((t, i) => (
                      <div key={i} className="flex gap-1.5">
                        <input type="time" value={t} onChange={e => updateDraftTime(draft.id, i, e.target.value)} className="void-focus w-full rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1.5 text-xs text-white outline-none" />
                        <button type="button" onClick={() => removeDraftTime(draft.id, i)} aria-label="Remove time" className="void-focus rounded-lg border border-white/10 px-2 text-white/40 hover:text-red-400">×</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="void-focus w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Save schedule'}
            </button>
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-white/50">Existing schedules</h3>
            {loading ? (
              <p className="text-xs text-white/40">Loading…</p>
            ) : loadError ? (
              <p className="text-xs text-red-400">{loadError}</p>
            ) : schedules.length === 0 ? (
              <p className="rounded-xl border border-dashed border-white/10 px-4 py-6 text-center text-xs text-white/40">No schedules yet.</p>
            ) : (
              <div className="space-y-2">
                {schedules.map(schedule => (
                  <div key={schedule.id} className="void-card rounded-xl p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-white">{schedule.name}</p>
                        <p className="text-[11px] text-white/40">{formatScheduleWindow(schedule)}</p>
                      </div>
                      <StatusBadge status={schedule.status} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-white/40">
                      <span>Next: {formatDateTime(schedule.next_run_at)} · Last: {formatDateTime(schedule.last_run_at)} {schedule.last_status ? `(${schedule.last_status})` : ''}</span>
                      <div className="flex items-center gap-1">
                        <button type="button" onClick={() => toggleStatus(schedule)} className="void-focus flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-white/60 hover:bg-white/5">
                          {schedule.status === 'active' ? <Pause size={11} /> : <CirclePlay size={11} />}
                          {schedule.status === 'active' ? 'Pause' : 'Start'}
                        </button>
                        <button type="button" onClick={() => viewLogs(schedule)} className="void-focus flex items-center gap-1 rounded-md bg-accent/15 px-2 py-1 text-accent-light hover:bg-accent/25">
                          <ScrollText size={11} />Logs
                        </button>
                        {isAdmin && (
                          <button type="button" onClick={() => remove(schedule)} className="void-focus flex items-center gap-1 rounded-md bg-red-500/10 px-2 py-1 text-red-400 hover:bg-red-500/20">
                            <Trash2 size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                    {schedule.last_status === 'failed' && schedule.last_error && (
                      <p className="mt-2 truncate text-[11px] text-red-400">Didn't run as scheduled: {schedule.last_error}</p>
                    )}
                    {selectedSchedule?.id === schedule.id && (
                      <div className="mt-3 border-t border-white/[0.06] pt-2 space-y-1.5">
                        {logs.length === 0 ? (
                          <p className="text-[11px] text-white/35">No runs yet.</p>
                        ) : logs.map(log => (
                          <div key={log.id} className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-white/50">
                            <StatusBadge status={log.status} />
                            <span>started {formatDateTime(log.started_at)}</span>
                            <span>{log.rows_written} rows</span>
                            {log.error_message && <span className="text-red-400">{log.error_message}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
