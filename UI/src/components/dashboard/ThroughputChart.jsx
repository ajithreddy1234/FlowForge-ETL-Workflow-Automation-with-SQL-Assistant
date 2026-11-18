const SERIES_COLORS = {
  success: '#34d399',
  failed: '#f87171',
  skipped: '#fbbf24',
}

export default function ThroughputChart({ series = [] }) {
  const hasData = series.some(d => d.total > 0)
  const max = Math.max(1, ...series.map(d => d.total))
  const width = 640
  const height = 160
  const barGap = 4
  const barWidth = series.length ? (width / series.length) - barGap : 0

  return (
    <div>
      <div className="mb-3 flex items-center gap-4 text-[11px] text-white/45">
        {Object.entries(SERIES_COLORS).map(([key, color]) => (
          <span key={key} className="flex items-center gap-1.5 capitalize">
            <span className="h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden="true" />
            {key}
          </span>
        ))}
      </div>
      {!hasData ? (
        <div className="flex h-40 items-center justify-center text-xs text-white/30">
          No executions recorded in the last 14 days.
        </div>
      ) : (
        <svg viewBox={`0 0 ${width} ${height + 20}`} className="w-full" role="img" aria-label="Executions per day, last 14 days">
          {series.map((day, i) => {
            const x = i * (barWidth + barGap)
            let yCursor = height
            const segments = ['success', 'failed', 'skipped'].map(key => {
              const value = day[key] || 0
              const segHeight = (value / max) * height
              yCursor -= segHeight
              return { key, y: yCursor, h: segHeight, value }
            })
            return (
              <g key={day.date}>
                <title>{`${day.date}: ${day.total} run${day.total === 1 ? '' : 's'}`}</title>
                <rect x={x} y={0} width={barWidth} height={height} fill="rgba(255,255,255,0.03)" rx={3} />
                {segments.map(seg => seg.h > 0 && (
                  <rect key={seg.key} x={x} y={seg.y} width={barWidth} height={Math.max(seg.h, 2)} fill={SERIES_COLORS[seg.key]} rx={2} />
                ))}
                <text x={x + barWidth / 2} y={height + 14} textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.35)" fontFamily="JetBrains Mono, monospace">
                  {day.date.slice(5)}
                </text>
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}
