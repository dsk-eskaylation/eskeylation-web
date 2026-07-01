import { useEffect, type ReactNode } from 'react'
import './Modal.css'

interface Props {
  onClose: () => void
  children: ReactNode
}

/** Modal shell dùng chung: overlay tối, panel bo góc, Escape + click nền để đóng. */
export function Modal({ onClose, children }: Props) {
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
      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal__close" onClick={onClose} aria-label="Đóng">
          ✕
        </button>
        {children}
      </div>
    </div>
  )
}
