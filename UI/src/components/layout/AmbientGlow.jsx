const POSITIONS = {
  'top': 'top-[-20%] left-1/2 -translate-x-1/2',
  'top-left': 'top-[-15%] left-[-10%]',
  'top-right': 'top-[-15%] right-[-10%]',
  'center': 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
  'bottom': 'bottom-[-20%] left-1/2 -translate-x-1/2',
}

export default function AmbientGlow({ position = 'top', size = 640, className = '' }) {
  return (
    <div
      aria-hidden="true"
      className={`void-glow ${POSITIONS[position] || POSITIONS.top} ${className}`}
      style={{ width: size, height: size }}
    />
  )
}
