import { useEffect, useRef } from 'react'
import { formatDateTime } from '../../utils/format'

function buildTranscript(run) {
  const lines = []
  if (run.queued_at) {
    lines.push({ ts: run.queued_at, text: `run queued${run.scheduled_for ? ` for ${formatDateTime(run.scheduled_for)}` : ''}`, tone: 'muted' })
  }
  if (run.started_at) {
    lines.push({ ts: run.started_at, text: `pipeline "${run.pipeline_name}" started`, tone: 'accent' })
  }
  if (run.status === 'running' && !run.finished_at) {
    lines.push({ ts: null, text: 'executing nodes…', tone: 'accent' })
  }
  if (run.status === 'skipped') {
    lines.push({ ts: run.finished_at, text: `run skipped — ${run.error_message || 'schedule inactive'}`, tone: 'warning' })
  } else if (run.status === 'failed') {
    lines.push({ ts: run.finished_at, text: 'run failed', tone: 'error' })
    if (run.error_message) lines.push({ ts: null, text: run.error_message, tone: 'error', indent: true })
  } else if (run.finished_at) {
    lines.push({ ts: run.finished_at, text: `run finished — ${run.rows_written ?? 0} rows written`, tone: 'success' })
  }
  return lines
}

const TONE_CLASS = {
  muted: 'text-white/40',
  accent: 'text-accent-light',
  success: 'text-emerald-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
}

export function buildTranscriptText(run) {
  return buildTranscript(run)
    .map(line => `${line.ts ? `[${formatDateTime(line.ts)}] ` : ''}${line.text}`)
    .join('\n')
}

export default function LogTerminal({ run }) {
  const scrollRef = useRef(null)
  const followRef = useRef(true)

  useEffect(() => {
    if (followRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [run])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32
  }

  if (!run) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-white/30">
        Select a run to view its timeline.
      </div>
    )
  }

  const lines = buildTranscript(run)

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="void-scanlines h-full overflow-y-auto rounded-xl bg-black/40 p-4 font-mono text-[12px] leading-relaxed"
    >
      {lines.map((line, i) => (
        <p key={i} className={`${TONE_CLASS[line.tone]} ${line.indent ? 'pl-4' : ''} whitespace-pre-wrap`}>
          {line.ts && <span className="text-white/25">[{formatDateTime(line.ts)}] </span>}
          {line.text}
        </p>
      ))}
      <p className="log-cursor text-white/30">$</p>
    </div>
  )
}
