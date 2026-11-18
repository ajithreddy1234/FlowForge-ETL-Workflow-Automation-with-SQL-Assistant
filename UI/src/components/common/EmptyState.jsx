export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 px-6 py-16 text-center">
      {Icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.06] text-white/40">
          <Icon size={22} aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-semibold text-white">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm text-white/45">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
