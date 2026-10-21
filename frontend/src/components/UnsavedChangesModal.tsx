import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Modal } from './Modal'

export function UnsavedChangesModal({ children, dirty, busy, label, onClose }: {
  children: (requestClose: () => void) => ReactNode
  dirty: boolean
  busy: boolean
  label: string
  onClose: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  const keepRef = useRef<HTMLButtonElement>(null)
  const previousField = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  useLayoutEffect(() => {
    if (confirming) keepRef.current?.focus()
    else if (previousField.current?.isConnected) previousField.current.focus()
  }, [confirming])
  function requestClose() {
    if (busy) return
    if (confirming) setConfirming(false)
    else if (dirty) {
      previousField.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
      setConfirming(true)
    } else onClose()
  }
  return (
    <Modal onClose={requestClose} label={confirming ? 'Thay đổi chưa lưu' : label}>
      {/* Keep the form mounted so focus and field values survive cancellation. */}
      <div hidden={confirming}>{children(requestClose)}</div>
      {confirming && <div className="cms-confirm">
        <h2 className="cms-editor__title">Thay đổi chưa lưu</h2>
        <p className="cms-confirm__msg">Bạn muốn tiếp tục chỉnh sửa hay bỏ những thay đổi chưa lưu?</p>
        <div className="cms-editor__foot">
          <button ref={keepRef} type="button" className="cms-pill cms-pill--active" onClick={() => setConfirming(false)}>Tiếp tục chỉnh sửa</button>
          <button type="button" className="cms-pill cms-pill--danger-solid" onClick={onClose}>Bỏ thay đổi</button>
        </div>
      </div>}
    </Modal>
  )
}
