import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import './Toast.css'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void | Promise<void>
}

export interface ToastOptions {
  tone?: ToastTone
  /** Tự tắt sau ms; mặc định 4s (7s nếu có nút hành động như Hoàn tác). */
  duration?: number
  action?: ToastAction
}

interface ToastItem {
  id: number
  message: string
  tone: ToastTone
  duration: number
  action?: ToastAction
}

interface ToastCtx {
  notify: (message: string, opts?: ToastOptions) => number
  dismiss: (id: number) => void
}

const Ctx = createContext<ToastCtx | null>(null)

let counter = 0

/** Provider toast toàn cục — render một chồng thông báo cố định ở GÓC DƯỚI-PHẢI. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const notify = useCallback((message: string, opts: ToastOptions = {}) => {
    const id = ++counter
    const duration = opts.duration ?? (opts.action ? 7000 : 4000)
    setToasts((prev) => [
      ...prev,
      { id, message, tone: opts.tone ?? 'info', duration, action: opts.action },
    ])
    return id
  }, [])

  return (
    <Ctx.Provider value={{ notify, dismiss }}>
      {children}
      <div className="toast-stack" role="region" aria-label="Thông báo">
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onClose={() => dismiss(t.id)} />
        ))}
      </div>
    </Ctx.Provider>
  )
}

function ToastCard({ toast, onClose }: { toast: ToastItem; onClose: () => void }) {
  const [busy, setBusy] = useState(false)
  // Giữ onClose trong ref -> timer tự tắt không bị reset mỗi lần cha re-render.
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    const id = setTimeout(() => closeRef.current(), toast.duration)
    return () => clearTimeout(id)
  }, [toast.duration])

  const onAction = async () => {
    if (!toast.action) return
    setBusy(true)
    try {
      await toast.action.onClick()
    } finally {
      closeRef.current()
    }
  }

  return (
    <div className={`toast toast--${toast.tone}`} role="status">
      <span className="toast__dot" aria-hidden="true" />
      <span className="toast__msg">{toast.message}</span>
      {toast.action && (
        <button
          type="button"
          className="toast__action"
          onClick={() => void onAction()}
          disabled={busy}
        >
          {toast.action.label}
        </button>
      )}
      <button
        type="button"
        className="toast__close"
        onClick={onClose}
        aria-label="Đóng thông báo"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" />
          <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>
    </div>
  )
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useToast phải nằm trong <ToastProvider>')
  return ctx
}
