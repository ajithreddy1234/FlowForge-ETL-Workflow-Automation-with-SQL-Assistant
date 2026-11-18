import GlassCard from '../common/GlassCard'

export default function KpiCard({ icon: Icon, label, value, hint, tone = 'default' }) {
  const toneClass = {
    default: 'text-white',
    success: 'text-emerald-400',
    error: 'text-red-400',
    accent: 'text-accent-light',
  }[tone]

  return (
    <GlassCard hover className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-white/45">{label}</p>
        {Icon && (
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.06] text-white/50">
            <Icon size={14} aria-hidden="true" />
          </div>
        )}
      </div>
      <p className={`mt-2 font-mono text-2xl font-bold ${toneClass}`}>{value}</p>
      {hint && <p className="mt-1 text-[11px] text-white/35">{hint}</p>}
    </GlassCard>
  )
}
