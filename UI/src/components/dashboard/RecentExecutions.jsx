import { useNavigate } from 'react-router-dom'
import StatusBadge from '../common/StatusBadge'
import EmptyState from '../common/EmptyState'
import { ScrollText } from 'lucide-react'
import { formatDateTime, formatDuration } from '../../utils/format'

export default function RecentExecutions({ runs = [] }) {
  const navigate = useNavigate()

  if (runs.length === 0) {
    return <EmptyState icon={ScrollText} title="No executions yet" description="Scheduled runs will show up here." />
  }

  return (
    <ul className="divide-y divide-white/[0.06]">
      {runs.map(run => (
        <li key={run.id}>
          <button
            type="button"
            onClick={() => navigate(`/logs/${run.id}`)}
            className="void-focus flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
          >
            <StatusBadge status={run.status} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-white">{run.pipeline_name || 'Unknown pipeline'}</p>
              <p className="font-mono text-[11px] text-white/35">run #{run.id} · {formatDateTime(run.started_at || run.created_at)}</p>
            </div>
            <div className="shrink-0 text-right font-mono text-[11px] text-white/40">
              <p>{formatDuration(run.duration_seconds)}</p>
              <p>{run.rows_written ?? 0} rows</p>
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}
