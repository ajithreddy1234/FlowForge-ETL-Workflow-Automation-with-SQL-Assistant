import { statusMeta } from '../../utils/statusMap'

export default function PipelineStatusChart({ breakdown = {} }) {
  const entries = Object.entries(breakdown)
  const total = entries.reduce((sum, [, count]) => sum + count, 0)

  if (total === 0) {
    return <div className="flex h-32 items-center justify-center text-xs text-white/30">No runs in the last 30 days.</div>
  }

  return (
    <ul className="space-y-2.5">
      {entries.map(([status, count]) => {
        const meta = statusMeta(status)
        const pct = total ? Math.round((count / total) * 100) : 0
        return (
          <li key={status}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className={`font-medium capitalize ${meta.textClass}`}>{meta.label}</span>
              <span className="font-mono text-white/45">{count} · {pct}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
              <div className={`h-full rounded-full ${meta.dotClass}`} style={{ width: `${pct}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
