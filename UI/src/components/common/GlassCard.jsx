export default function GlassCard({ as: Tag = 'div', hover = false, glow = false, className = '', children, ...rest }) {
  return (
    <Tag
      className={`void-card rounded-2xl transition-all duration-200 ${
        hover ? 'hover:border-white/20 hover:-translate-y-0.5 hover:shadow-[0_16px_40px_rgba(0,0,0,0.35)]' : ''
      } ${glow ? 'shadow-glow-accent-sm border-accent/40' : ''} ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  )
}
