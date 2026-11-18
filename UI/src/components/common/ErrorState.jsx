import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ErrorState({ title = 'Something went wrong', description, onRetry }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/[0.04] px-6 py-14 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/15 text-red-400">
        <AlertTriangle size={22} aria-hidden="true" />
      </div>
      <p className="text-sm font-semibold text-white">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-white/50">{description}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="void-focus mt-5 inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-white/10"
        >
          <RefreshCw size={13} aria-hidden="true" />
          Try again
        </button>
      )}
    </div>
  )
}
