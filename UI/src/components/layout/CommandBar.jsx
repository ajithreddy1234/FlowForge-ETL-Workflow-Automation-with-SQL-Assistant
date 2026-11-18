import { Search } from 'lucide-react'

export default function CommandBar({
  value,
  onChange,
  placeholder = 'Search...',
  actions = null,
  autoFocus = false,
  className = '',
}) {
  return (
    <div className={`void-glass flex items-center gap-2 rounded-2xl px-4 py-2.5 ${className}`}>
      <Search size={16} className="text-white/40 shrink-0" aria-hidden="true" />
      <input
        type="search"
        value={value}
        onChange={e => onChange?.(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        autoFocus={autoFocus}
        className="void-focus min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-white/35 outline-none"
      />
      {actions && <div className="flex items-center gap-1.5 shrink-0">{actions}</div>}
    </div>
  )
}
