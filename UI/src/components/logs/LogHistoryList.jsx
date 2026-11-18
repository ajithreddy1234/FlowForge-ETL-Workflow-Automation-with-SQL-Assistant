import StatusBadge from '../common/StatusBadge'
import EmptyState from '../common/EmptyState'
import { ScrollText } from 'lucide-react'
import { formatDateTime } from '../../utils/format'

export default function LogHistoryList({ runs, selectedId, onSelect }) {
  if (runs.length === 0) {
    return <EmptyState icon={ScrollText} title="No runs found" description="Adjust your filters or search." />
  }

  return (
    <ul className="space-y-1.5" role="listbox" aria-label="Execution history">
      {runs.map(run => {
        const selected = run.id === selectedId
        return (
          <li key={run.id}>
            <button
              type="button"
              role="option"
              aria-selected={selected}
              onClick={() => onSelect(run.id)}
              className={`void-focus w-full rounded-xl border p-3 text-left transition-colors ${
                selected
                  ? 'border-accent/50 bg-accent/10 shadow-glow-accent-sm'
                  : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-xs font-semibold text-white">{run.pipeline_name || 'Unknown pipeline'}</p>
                <StatusBadge status={run.status} />
              </div>
              <p className="mt-1 font-mono text-[10px] text-white/35">
                run #{run.id} · {formatDateTime(run.started_at || run.created_at)}
              </p>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
