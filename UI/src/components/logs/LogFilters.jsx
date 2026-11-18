import CommandBar from '../layout/CommandBar'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'success', label: 'Success' },
  { id: 'failed', label: 'Errors' },
  { id: 'skipped', label: 'Skipped' },
  { id: 'running', label: 'Running' },
  { id: 'queued', label: 'Queued' },
]

export default function LogFilters({ status, onStatusChange, search, onSearchChange }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Filter by status">
        {FILTERS.map(f => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={status === f.id}
            onClick={() => onStatusChange(f.id)}
            className={`void-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              status === f.id ? 'bg-accent/20 text-accent-light' : 'text-white/50 hover:bg-white/5'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <CommandBar value={search} onChange={onSearchChange} placeholder="Search pipeline or error…" className="sm:max-w-xs" />
    </div>
  )
}
