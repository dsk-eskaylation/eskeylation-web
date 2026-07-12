import { useState } from 'react'
import { Modal } from './Modal'

interface Props {
  title: string
  message: string
  /** Nhãn nút xác nhận (mặc định "Xoá"). */
  confirmLabel?: string
  /** 'danger' tô đỏ nút xác nhận (mặc định). */
  tone?: 'danger' | 'default'
  onConfirm: () => void | Promise<void>
  onClose: () => void
}

/** Hộp xác nhận đồng bộ giao diện CMS — thay cho window.confirm() của trình duyệt. */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Xoá',
  tone = 'danger',
  onConfirm,
  onClose,
}: Props) {
  const [busy, setBusy] = useState(false)

  const confirm = async () => {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal onClose={onClose} showClose={false}>
      <div className="cms-confirm">
        <h2 className="cms-editor__title">{title}</h2>
        <p className="cms-confirm__msg">{message}</p>
        <div className="cms-editor__foot">
          <button type="button" className="cms-pill" onClick={onClose} disabled={busy}>
            Huỷ
          </button>
          <button
            type="button"
            className={
              tone === 'danger' ? 'cms-pill cms-pill--danger-solid' : 'cms-pill cms-pill--active'
            }
            onClick={() => void confirm()}
            disabled={busy}
          >
            {busy ? 'Đang xử lý…' : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}
