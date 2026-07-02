import { useEffect, useState } from 'react'
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

const CARD_W = 536 // Figma: card 536px
const GAP = 146 // Figma #1:1846 gap 146

/** Feed carousel (Figma "Ảnh"/"Cộng đồng"): bài giữa nét, hai bên blur;
    trượt mượt bằng translateX; click bên cạnh để chuyển, click giữa mở modal.
    Dùng chung cho cả Ảnh và Cộng đồng (tái dùng modal, không duplicate). */
export function Feed({ type, emptyTitle }: Props) {
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const state = useApi(() => api.list(type, { pageSize: 30 }), [type])

  const items = state.status === 'success' ? state.data.items : []
  const idx = Math.min(active, Math.max(0, items.length - 1))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (open) return
      if (e.key === 'ArrowLeft') setActive((v) => Math.max(0, v - 1))
      if (e.key === 'ArrowRight')
        setActive((v) => Math.min(items.length - 1, v + 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [items.length, open])

  if (state.status === 'loading') return <div className="feed" aria-busy="true" />
  if (state.status === 'error') return <EmptyState title="Không tải được nội dung." />
  if (items.length === 0) return <EmptyState title={emptyTitle} />

  const cur = items[idx]
  const step = CARD_W + GAP

  return (
    <div className="feed">
      <div className="feed__viewport">
        <div
          className="feed__track"
          style={{ transform: `translateX(${-idx * step}px)` }}
        >
          {items.map((item, i) => {
            const dist = Math.abs(i - idx)
            const cls =
              dist === 0
                ? 'feed__slide feed__slide--active'
                : dist === 1
                  ? 'feed__slide feed__slide--near'
                  : 'feed__slide feed__slide--far'
            return (
              <div
                className={cls}
                key={item.id}
                onClick={() => (i === idx ? setOpen(true) : setActive(i))}
              >
                <PostCard content={item} />
              </div>
            )
          })}
        </div>
      </div>

      {items.length > 1 && (
        <div className="feed__dots" role="tablist" aria-label="Chọn bài viết">
          {items.map((item, i) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={i === idx}
              className={i === idx ? 'feed__dot feed__dot--active' : 'feed__dot'}
              onClick={() => setActive(i)}
              aria-label={`Bài ${i + 1}`}
            />
          ))}
        </div>
      )}

      {open && (
        <Modal onClose={() => setOpen(false)}>
          <PostGallery content={cur} />
        </Modal>
      )}
    </div>
  )
}
