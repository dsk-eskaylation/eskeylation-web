import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import './Modal.css'

interface Props {
  onClose: () => void
  children: ReactNode
  /** 'panel': khung nền #101010 bo góc (Figma xem full ảnh).
      'bare': không khung, nội dung nổi thẳng trên overlay (Figma video đã chọn). */
  variant?: 'panel' | 'bare'
  showClose?: boolean
  label?: string
}

/** Modal shell dùng chung: overlay tối, Escape + click nền để đóng, animation vào. */
export function Modal({
  onClose,
  children,
  variant = 'panel',
  showClose = true,
  label = 'Nội dung',
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  // Giữ onClose trong ref để effect chỉ subscribe 1 lần,
  // không gỡ/gắn lại listener mỗi khi cha re-render tạo callback mới.
  const onCloseRef = useRef(onClose)
  useLayoutEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useLayoutEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const previousOverflow = document.body.style.overflow
    const root = rootRef.current
    const siblings = [...document.body.children].filter(
      (element): element is HTMLElement => element instanceof HTMLElement && !element.contains(root),
    ).map((element) => ({ element, inert: element.inert }))
    siblings.forEach(({ element }) => { element.inert = true })
    const focusable = () =>
      [
        ...(root?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), video[controls], [tabindex="0"]',
        ) ?? []),
      ].filter((element) => element.getClientRects().length > 0)
    ;(focusable()[0] ?? root)?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => {
      if ([...document.querySelectorAll('.modal')].at(-1) !== root) return
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current()
      }
      if (e.key !== 'Tab') return
      const elements = focusable()
      const first = elements[0] ?? root
      const last = elements[elements.length - 1] ?? root
      if (
        e.shiftKey &&
        (document.activeElement === first || document.activeElement === root)
      ) {
        e.preventDefault()
        last?.focus({ preventScroll: true })
      } else if (
        !e.shiftKey &&
        (document.activeElement === last || document.activeElement === root)
      ) {
        e.preventDefault()
        first?.focus({ preventScroll: true })
      }
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
      siblings.forEach(({ element, inert }) => { element.inert = inert })
      if (previousFocus?.isConnected)
        previousFocus.focus({ preventScroll: true })
    }
  }, [])

  return createPortal(
    <div
      ref={rootRef}
      className="modal"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={label}
      tabIndex={-1}
    >
      <div
        className={
          variant === 'bare'
            ? 'modal__panel modal__panel--bare'
            : 'modal__panel'
        }
        onClick={(e) => e.stopPropagation()}
      >
        {showClose && (
          <button className="modal__close" onClick={onClose} aria-label="Đóng">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <line
                x1="5"
                y1="5"
                x2="19"
                y2="19"
                stroke="currentColor"
                strokeWidth="2"
              />
              <line
                x1="19"
                y1="5"
                x2="5"
                y2="19"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
          </button>
        )}
        {children}
      </div>
    </div>,
    document.body,
  )
}
