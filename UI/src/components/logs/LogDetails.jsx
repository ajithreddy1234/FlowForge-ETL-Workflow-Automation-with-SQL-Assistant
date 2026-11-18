import { useNavigate } from 'react-router-dom'
import { Copy, Download, ExternalLink, RotateCcw } from 'lucide-react'
import StatusBadge from '../common/StatusBadge'
import { formatDateTime, formatDuration } from '../../utils/format'
import { buildTranscriptText } from './LogTerminal'
import { useToast } from '../common/Toast'

function Field({ label, value }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-white/35">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs text-white/75">{value}</p>
    </div>
  )
}

export default function LogDetails({ run, onRerun, rerunning }) {
  const navigate = useNavigate()
  const toast = useToast()

  if (!run) return null

  const copyLogs = async () => {
    try {
      await navigator.clipboard.writeText(buildTranscriptText(run))
      toast.push('Run timeline copied', { type: 'success' })
    } catch {
      toast.push('Could not copy to clipboard', { type: 'error' })
    }
  }

  const downloadLogs = () => {
    const blob = new Blob([buildTranscriptText(run)], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `run_${run.id}.log.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="border-t border-white/[0.06] px-4 py-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          <span className="font-mono text-xs text-white/50">run #{run.id}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={copyLogs} title="Copy timeline" aria-label="Copy run timeline" className="void-focus rounded-lg border border-white/10 p-1.5 text-white/50 hover:bg-white/5">
            <Copy size={13} />
          </button>
          <button type="button" onClick={downloadLogs} title="Download timeline" aria-label="Download run timeline" className="void-focus rounded-lg border border-white/10 p-1.5 text-white/50 hover:bg-white/5">
            <Download size={13} />
          </button>
          {run.pipeline_slug && (
            <button type="button" onClick={() => navigate(`/pipelines/${encodeURIComponent(run.pipeline_slug)}`)} title="Open pipeline" aria-label="Open pipeline in editor" className="void-focus rounded-lg border border-white/10 p-1.5 text-white/50 hover:bg-white/5">
              <ExternalLink size={13} />
            </button>
          )}
          {run.status === 'failed' && onRerun && (
            <button
              type="button"
              onClick={onRerun}
              disabled={rerunning}
              className="void-focus flex items-center gap-1.5 rounded-lg bg-accent/15 px-2.5 py-1.5 text-xs font-semibold text-accent-light hover:bg-accent/25 disabled:opacity-50"
            >
              <RotateCcw size={12} className={rerunning ? 'animate-spin' : ''} />
              {rerunning ? 'Running…' : 'Run again'}
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Pipeline" value={run.pipeline_name || '—'} />
        <Field label="Duration" value={formatDuration(run.duration_seconds)} />
        <Field label="Started" value={formatDateTime(run.started_at)} />
        <Field label="Finished" value={formatDateTime(run.finished_at)} />
      </div>
    </div>
  )
}
