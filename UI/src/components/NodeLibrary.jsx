import { useMemo, useState } from 'react'
import { KeyRound, Database, Zap, Sheet, PanelLeftClose, Search } from 'lucide-react'
import { NODE_COLORS } from '../constants'

const GROUPS = [
  {
    id: 'connection',
    label: 'Connection',
    items: [
      { type: 'credential', icon: KeyRound, name: 'Credential', desc: import.meta.env.VITE_PUBLIC_DEMO === 'true' ? 'Read-only synthetic orders source' : 'PostgreSQL / MySQL / Redshift connection' },
    ],
  },
  {
    id: 'extract',
    label: 'Extract',
    items: [
      { type: 'extract', icon: Database, name: 'Extract', desc: 'Select a table or run a read-only SQL query' },
    ],
  },
  {
    id: 'transform',
    label: 'Transform',
    items: [
      { type: 'transform', icon: Zap, name: 'Operation', desc: 'Filter, join, group, pivot and 15+ more operations' },
    ],
  },
  {
    id: 'load',
    label: 'Load',
    items: [
      { type: 'load', icon: Sheet, name: import.meta.env.VITE_PUBLIC_DEMO === 'true' ? 'CSV destination' : 'Google Sheet', desc: 'Write the transformed table to a destination' },
    ],
  },
]

export default function NodeLibrary({ onCollapse, onAddNode }) {
  const [search, setSearch] = useState('')

  const onDragStart = (e, type) => {
    e.dataTransfer.setData('node-type', type)
    e.dataTransfer.effectAllowed = 'move'
  }

  const filteredGroups = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return GROUPS
    return GROUPS
      .map(group => ({ ...group, items: group.items.filter(item => item.name.toLowerCase().includes(q) || item.desc.toLowerCase().includes(q)) }))
      .filter(group => group.items.length > 0)
  }, [search])

  return (
    <div className="void-glass flex w-60 shrink-0 flex-col rounded-2xl">
      <div className="flex items-start justify-between gap-2 border-b border-white/[0.07] px-3 py-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/70">Components</p>
          <p className="mt-0.5 text-[11px] text-white/35">Drag or click to add</p>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          title="Hide component palette"
          aria-label="Hide component palette"
          className="void-focus shrink-0 rounded-md p-1.5 text-white/50 hover:bg-white/5"
        >
          <PanelLeftClose size={14} />
        </button>
      </div>

      <div className="border-b border-white/[0.07] px-3 py-2.5">
        <div className="flex items-center gap-1.5 rounded-lg bg-white/[0.04] px-2.5 py-1.5">
          <Search size={12} className="shrink-0 text-white/30" aria-hidden="true" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search components…"
            aria-label="Search components"
            className="void-focus min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-white/25"
          />
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        {filteredGroups.length === 0 && (
          <p className="px-1 text-xs text-white/30">No components match "{search}".</p>
        )}
        {filteredGroups.map(group => (
          <div key={group.id}>
            <p className="mb-1.5 px-1 text-[10px] font-bold uppercase tracking-wider text-white/30">{group.label}</p>
            <div className="flex flex-col gap-1.5">
              {group.items.map(item => {
                const C = NODE_COLORS[item.type]
                const Icon = item.icon
                return (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={e => onDragStart(e, item.type)}
                    onClick={() => onAddNode?.(item.type)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onAddNode?.(item.type) } }}
                    className="void-focus flex cursor-grab items-center gap-2.5 rounded-xl p-2.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_20px_rgba(0,0,0,0.3)] active:cursor-grabbing"
                    style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}` }}
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ background: C.header }}>
                      <Icon size={13} style={{ color: C.text }} aria-hidden="true" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold" style={{ color: C.text }}>{item.name}</p>
                      <p className="mt-0.5 truncate text-[10px] text-white/35">{item.desc}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-white/[0.07] px-3 py-2.5">
        <p className="text-[10px] text-white/30">Connect nodes left → right to build your pipeline.</p>
      </div>
    </div>
  )
}
