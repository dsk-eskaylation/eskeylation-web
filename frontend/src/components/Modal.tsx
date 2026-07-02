import { useEffect, type ReactNode } from 'react'
import './Modal.css'

interface Props {
  onClose: () => void
  children: ReactNode
  /** 'panel': khung nền #101010 bo góc (Figma xem full ảnh).
      'bare': không khung, nội dung nổi thẳng trên overlay (Figma video đã chọn). */
  variant?: 'panel' | 'bare'
  showClose?: boolean
}

/** Modal shell dùng chung: overlay tối, Escape + click nền để đóng, animation vào. */
export function Modal({ onClose, children, variant = 'panel', showClose = true }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  return (
    <div className="modal" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className={variant === 'bare' ? 'modal__panel modal__panel--bare' : 'modal__panel'}
        onClick={(e) => e.stopPropagation()}
      >
        {showClose && (
          <button className="modal__close" onClick={onClose} aria-label="Đóng">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <line x1="5" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" />
              <line x1="19" y1="5" x2="5" y2="19" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
        )}
        {children}
      </div>
    </div>
  )
}
