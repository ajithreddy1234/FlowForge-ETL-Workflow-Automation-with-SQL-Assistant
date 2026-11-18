/**
 * Renders inside a node to show processing state:
 * - running → sweeping shimmer + indeterminate bottom bar
 * - done    → green tint + solid green bar
 * - error   → red tint + solid red bar
 *
 * Must be placed inside an overflow:hidden container so the shimmer is clipped.
 * Content siblings should have position:relative + zIndex:1 to stay above the overlay.
 */
export default function NodeRunOverlay({ status, accentColor }) {
  if (!status || status === 'idle') return null

  const isDone    = status === 'done'
  const isError   = status === 'error'
  const isRunning = status === 'running'

  const barColor  = isDone ? '#34d399' : isError ? '#f87171' : (accentColor || '#8B5CF6')
  const tintColor = isDone ? 'rgba(52,211,153,0.12)' : 'rgba(248,113,113,0.1)'

  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      zIndex: 2,
      overflow: 'hidden',
      borderRadius: 'inherit',
    }}>
      {/* Background tint for done / error */}
      {!isRunning && (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: tintColor,
          transition: 'background 0.4s ease',
        }} />
      )}

      {/* Sweeping shimmer while running */}
      {isRunning && (
        <div
          className="node-sweep"
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            width: '55%',
            background:
              'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.38) 50%, transparent 100%)',
          }}
        />
      )}

      {/* Bottom progress bar */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: 3,
        overflow: 'hidden',
      }}>
        {isRunning ? (
          <div
            className="node-bar-anim"
            style={{
              position: 'absolute',
              top: 0,
              height: '100%',
              background: barColor,
              borderRadius: 2,
              opacity: 0.85,
            }}
          />
        ) : (
          <div style={{
            width: '100%',
            height: '100%',
            background: barColor,
            transition: 'background 0.3s ease',
          }} />
        )}
      </div>
    </div>
  )
}
