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

/* Kích thước card + gap theo viewport (đồng bộ với Feed.css):
   desktop 536/146 (Figma), tablet 460/60, mobile 88vw/24 */
function slideMetrics(vw: number) {
  if (vw <= 640) return { card: vw * 0.88, gap: 24 }
  if (vw <= 900) return { card: 460, gap: 60 }
  return { card: 536, gap: 146 }
}

function useSlideStep() {
  const [vw, setVw] = useState(() => window.innerWidth)
  useEffect(() => {
    const onResize = () => setVw(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  const { card, gap } = slideMetrics(vw)
  return card + gap
}

/** Feed carousel (Figma "Ảnh"/"Cộng đồng"): bài giữa nét, hai bên blur;
    trượt mượt bằng translateX; click bên cạnh để chuyển, click giữa mở modal.
    Dùng chung cho cả Ảnh và Cộng đồng (tái dùng modal, không duplicate). */
export function Feed({ type, emptyTitle }: Props) {
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const [touchX, setTouchX] = useState<number | null>(null)
  const step = useSlideStep()
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

  return (
    <div className="feed">
      <div
        className="feed__viewport"
        onTouchStart={(e) => setTouchX(e.touches[0].clientX)}
        onTouchEnd={(e) => {
          if (touchX === null) return
          const dx = e.changedTouches[0].clientX - touchX
          if (dx < -40) setActive((v) => Math.min(items.length - 1, v + 1))
          if (dx > 40) setActive((v) => Math.max(0, v - 1))
          setTouchX(null)
        }}
      >
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
