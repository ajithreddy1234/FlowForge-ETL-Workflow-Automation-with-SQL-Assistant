import { useNavigate } from 'react-router-dom'
import EmptyState from '../common/EmptyState'
import { Boxes } from 'lucide-react'
import { formatDateTime } from '../../utils/format'

export default function ActivePipelineTable({ pipelines = [] }) {
  const navigate = useNavigate()

  if (pipelines.length === 0) {
    return <EmptyState icon={Boxes} title="No active schedules" description="Schedule a saved pipeline to see it here." />
  }

  return (
    <ul className="divide-y divide-white/[0.06]">
      {pipelines.map(p => (
        <li key={p.name}>
          <button
            type="button"
            onClick={() => navigate(`/pipelines/${encodeURIComponent(p.name)}`)}
            className="void-focus flex w-full items-center justify-between gap-3 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
          >
            <p className="min-w-0 truncate text-xs font-semibold text-white">{p.pipeline_name}</p>
            <p className="shrink-0 font-mono text-[11px] text-white/40">next {formatDateTime(p.nextRun)}</p>
          </button>
        </li>
      ))}
    </ul>
  )
}
