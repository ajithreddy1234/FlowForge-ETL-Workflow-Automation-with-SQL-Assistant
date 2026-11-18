// Centralized status → color/label mapping used across the dashboard,
// pipeline list, runtime logs, and the editor's run indicators.
// Backend statuses observed in ScheduleRunLog / node runStatus:
//   queued, running, success, failed, skipped, done, error, active, paused, completed

const STATUS_META = {
  queued:    { label: 'Queued',    dotClass: 'bg-white/40',    textClass: 'text-white/70',   badgeClass: 'bg-white/10 text-white/70 border-white/10' },
  claimed:   { label: 'Starting',  dotClass: 'bg-accent/70',   textClass: 'text-accent-light', badgeClass: 'bg-accent/10 text-accent-light border-accent/20' },
  retry_wait:{ label: 'Retrying',  dotClass: 'bg-amber-400',   textClass: 'text-amber-300', badgeClass: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
  running:   { label: 'Running',   dotClass: 'bg-accent',      textClass: 'text-accent-light', badgeClass: 'bg-accent/15 text-accent-light border-accent/30' },
  success:   { label: 'Success',   dotClass: 'bg-emerald-400', textClass: 'text-emerald-400', badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  done:      { label: 'Success',   dotClass: 'bg-emerald-400', textClass: 'text-emerald-400', badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  active:    { label: 'Active',    dotClass: 'bg-emerald-400', textClass: 'text-emerald-400', badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  failed:    { label: 'Failed',    dotClass: 'bg-red-400',     textClass: 'text-red-400',     badgeClass: 'bg-red-500/15 text-red-400 border-red-500/30' },
  error:     { label: 'Error',     dotClass: 'bg-red-400',     textClass: 'text-red-400',     badgeClass: 'bg-red-500/15 text-red-400 border-red-500/30' },
  skipped:   { label: 'Skipped',   dotClass: 'bg-amber-400',   textClass: 'text-amber-400',   badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
  paused:    { label: 'Paused',    dotClass: 'bg-white/40',    textClass: 'text-white/60',    badgeClass: 'bg-white/10 text-white/60 border-white/10' },
  completed: { label: 'Completed', dotClass: 'bg-white/40',    textClass: 'text-white/60',    badgeClass: 'bg-white/10 text-white/60 border-white/10' },
  idle:      { label: 'Idle',      dotClass: 'bg-white/25',    textClass: 'text-white/40',    badgeClass: 'bg-white/5 text-white/40 border-white/10' },
}

export function statusMeta(status) {
  return STATUS_META[status] || {
    label: status ? String(status) : 'Unknown',
    dotClass: 'bg-white/25',
    textClass: 'text-white/40',
    badgeClass: 'bg-white/5 text-white/40 border-white/10',
  }
}

export const RUN_TERMINAL_STATUSES = new Set(['success', 'failed', 'skipped', 'done', 'error', 'completed'])

export function isTerminalStatus(status) {
  return RUN_TERMINAL_STATUSES.has(status)
}
