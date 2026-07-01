import { useState } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { PostCard } from '../components/PostCard'
import { Modal } from '../components/Modal'
import { PostGallery } from '../components/PostGallery'
import { EmptyState } from '../components/EmptyState'
import './Feed.css'

interface Props {
  type: 'photos' | 'community'
  emptyTitle: string
}

/** Feed dạng carousel: bài active ở giữa (nét), 2 bên blur; click active mở modal.
    Dùng chung cho cả Ảnh và Cộng đồng (tái dùng modal, không duplicate). */
export function Feed({ type, emptyTitle }: Props) {
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const state = useApi(() => api.list(type, { pageSize: 30 }), [type])

  if (state.status === 'loading') return <p className="muted feed__status">Đang tải…</p>
  if (state.status === 'error')
    return <EmptyState title="Không tải được nội dung." />

  const items = state.data.items
  if (items.length === 0)
    return (
      <EmptyState
        title={emptyTitle}
        hint="Nội dung sẽ xuất hiện khi được xuất bản."
      />
    )

  const idx = Math.min(active, items.length - 1)
  const cur = items[idx]

  return (
    <div className="feed">
      <div className="feed__carousel">
        {idx > 0 && (
          <div className="feed__side" onClick={() => setActive(idx - 1)}>
            <PostCard content={items[idx - 1]} blurred />
          </div>
        )}
        <div className="feed__active">
          <PostCard content={cur} onClick={() => setOpen(true)} />
        </div>
        {idx < items.length - 1 && (
          <div className="feed__side" onClick={() => setActive(idx + 1)}>
            <PostCard content={items[idx + 1]} blurred />
          </div>
        )}
      </div>

      <div className="feed__controls">
        <button
          type="button"
          onClick={() => setActive(Math.max(0, idx - 1))}
          disabled={idx === 0}
          aria-label="Trước"
        >
          ‹
        </button>
        <span className="muted">
          {idx + 1} / {items.length}
        </span>
        <button
          type="button"
          onClick={() => setActive(Math.min(items.length - 1, idx + 1))}
          disabled={idx === items.length - 1}
          aria-label="Sau"
        >
          ›
        </button>
      </div>

      {open && (
        <Modal onClose={() => setOpen(false)}>
          <PostGallery content={cur} />
        </Modal>
      )}
    </div>
  )
}
