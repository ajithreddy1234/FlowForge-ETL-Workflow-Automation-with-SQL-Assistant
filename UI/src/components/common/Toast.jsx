import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const ICONS = {
  success: { Icon: CheckCircle2, className: 'text-emerald-400' },
  error: { Icon: XCircle, className: 'text-red-400' },
  info: { Icon: Info, className: 'text-accent-light' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const push = useCallback((message, { type = 'info', duration = 4000 } = {}) => {
    const id = ++idRef.current
    setToasts(prev => [...prev, { id, message, type }])
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration)
    }
    return id
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ push, dismiss }}>
      {children}
      <div
        className="fixed bottom-24 right-5 z-[200] flex w-full max-w-xs flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map(toast => {
          const { Icon, className } = ICONS[toast.type] || ICONS.info
          return (
            <div
              key={toast.id}
              role="status"
              className="void-glass flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm text-white shadow-[0_12px_32px_rgba(0,0,0,0.45)] animate-fade-up"
            >
              <Icon size={16} className={`mt-0.5 shrink-0 ${className}`} aria-hidden="true" />
              <p className="min-w-0 flex-1 leading-snug">{toast.message}</p>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss notification"
                className="void-focus shrink-0 rounded p-0.5 text-white/40 hover:text-white"
              >
                <X size={13} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
