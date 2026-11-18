import { statusMeta } from '../../utils/statusMap'

export default function StatusBadge({ status, pulse = false }) {
  const meta = statusMeta(status)
  return (
    <span
      className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${meta.badgeClass}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${meta.dotClass} ${pulse ? 'animate-pulse-glow' : ''}`}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  )
}
