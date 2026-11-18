import { ArrowRight, Bot, Database, Sheet, Waypoints } from 'lucide-react'

const STEPS = [
  { icon: Database, label: 'Connect', detail: 'Save a read-only database connection' },
  { icon: Bot, label: 'Ask', detail: 'Describe the data you need in plain English' },
  { icon: Waypoints, label: 'Transform', detail: 'Add no-code cleanup and business rules' },
  { icon: Sheet, label: 'Load', detail: 'Preview and send the result to Google Sheets' },
]

export default function PipelineOnboarding({ onGuidedStart, onBlankStart }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/20 p-5 backdrop-blur-[2px]">
      <div className="void-glass w-full max-w-2xl rounded-2xl p-6 shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-accent-light">Guided ETL Builder</p>
        <h2 className="mt-2 text-xl font-bold text-white">Build a pipeline without starting from a blank canvas</h2>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-white/50">
          The guided flow creates the required source, query, and destination steps. Configure each card from left to right.
        </p>

        <div className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, label, detail }, index) => (
            <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/15 text-accent-light"><Icon size={12} /></span>
                <span className="text-xs font-semibold text-white/75">{index + 1}. {label}</span>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-white/35">{detail}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onGuidedStart}
            className="void-focus flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover"
          >
            Create guided pipeline <ArrowRight size={14} />
          </button>
          <button
            type="button"
            onClick={onBlankStart}
            className="void-focus rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-white/55 hover:bg-white/5"
          >
            Use advanced blank canvas
          </button>
        </div>
      </div>
    </div>
  )
}
