import { AlertTriangle, X, Copy, CheckCircle } from 'lucide-react'
import { useState } from 'react'

function actionHint(message) {
  if (!message) return null
  const m = message.toLowerCase()
  if (m.includes('permission') || m.includes('forbidden') || m.includes('caller does not have'))
    return {
      title: 'Google Sheets permission denied',
      body:  'Share the target Google Sheet with your service-account email as Editor. The email is in credentials/Sheet_Service.json under "client_email".',
    }
  if (m.includes('connection refused') || m.includes('could not connect') || m.includes('OperationalError'.toLowerCase()))
    return {
      title: 'Database connection failed',
      body:  'Check the host, port, database name, username and password in your Credential node. Make sure the database server is running and accessible.',
    }
  if (m.includes('websocket') || m.includes('failed to connect') || m.includes('1006') || m.includes('network'))
    return {
      title: 'Could not reach the pipeline server',
      body:  'The API server may have stopped. Run: python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload in the project directory.',
    }
  if (m.includes('no nodes') || m.includes('empty'))
    return {
      title: 'Nothing to run',
      body:  'Add at least one Extract node connected to a Sink node, then click Run Pipeline.',
    }
  if (m.includes('credential') || m.includes('db_profile'))
    return {
      title: 'Credential not configured',
      body:  'Connect a Credential node to your Extract node and fill in the host, database, username, and password fields.',
    }
  if (m.includes('spreadsheet') || m.includes('sheet_id') || m.includes('tab_name'))
    return {
      title: 'Google Sheets target not set',
      body:  'Open your Sink node and fill in the Spreadsheet ID and Tab Name fields.',
    }
  return null
}

export default function ErrorDialog({ errors, onClose }) {
  const [copied, setCopied] = useState(false)
  if (!errors || errors.length === 0) return null

  const fullText = errors.map(e => `[${e.nodeLabel || e.nodeId || 'pipeline'}] ${e.message}`).join('\n')

  const copyAll = () => {
    navigator.clipboard.writeText(fullText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="pipeline-error-title"
        className="void-glass w-full max-w-md overflow-hidden rounded-2xl shadow-[0_24px_64px_rgba(0,0,0,0.55)] animate-fade-up"
      >
        <div className="flex items-center gap-2.5 px-4 py-3.5" style={{ background: 'rgba(239,68,68,0.08)', borderBottom: '1px solid rgba(239,68,68,0.2)' }}>
          <AlertTriangle size={18} className="shrink-0 text-red-400" aria-hidden="true" />
          <span id="pipeline-error-title" className="flex-1 text-sm font-bold text-white">
            {errors.length === 1 ? 'Pipeline Error' : `${errors.length} Errors`}
          </span>
          <button onClick={onClose} aria-label="Close error dialog" className="void-focus rounded-lg p-1 text-white/40 hover:bg-white/5 hover:text-white">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-3.5 p-4" style={{ maxHeight: '55vh', overflowY: 'auto' }}>
          {errors.map((err, i) => {
            const hint = actionHint(err.message)
            return (
              <div key={i}>
                {err.nodeLabel && (
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-white/40">
                    {err.nodeLabel}
                  </p>
                )}
                <div className="rounded-lg px-3 py-2.5" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
                  <p className="whitespace-pre-wrap break-words font-mono text-xs text-red-300">
                    {err.message}
                  </p>
                </div>
                {hint && (
                  <div className="mt-2 rounded-lg px-3 py-2.5" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
                    <p className="mb-0.5 text-xs font-bold text-amber-300">{hint.title}</p>
                    <p className="text-xs leading-relaxed text-amber-200/80">{hint.body}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="flex items-center justify-between border-t border-white/[0.07] px-4 py-3">
          <button
            onClick={copyAll}
            className="void-focus flex items-center gap-1.5 rounded-md text-xs"
            style={{ color: copied ? '#34d399' : 'rgba(255,255,255,0.5)' }}
          >
            {copied ? <CheckCircle size={13} /> : <Copy size={13} />}
            {copied ? 'Copied!' : 'Copy error'}
          </button>
          <button
            onClick={onClose}
            className="void-focus rounded-lg bg-accent px-5 py-1.5 text-sm font-semibold text-white hover:bg-accent-hover"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
