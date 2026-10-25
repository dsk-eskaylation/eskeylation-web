import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import type { ContentOut, MediaOut } from '../api/types'
import { MediaImage } from '../components/MediaImage'
import { Modal } from '../components/Modal'
import { EmptyState } from '../components/EmptyState'
import './Photos.css'

interface Photo {
  id: string
  media: MediaOut
  url: string
  alt: string
  caption: string | null
  postTitle: string
  author: string
  date: string | null
}

/* Mảng rỗng ổn định — tránh useMemo chạy lại vì tạo [] mới mỗi render */
const EMPTY_ITEMS: ContentOut[] = []

const PER_PAGE = 12

function fmtDate(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
}

/** Trang Ảnh — THƯ VIỆN ảnh (masonry) thay vì gói trong từng bài viết:
    trải toàn bộ ảnh của mọi bài gallery thành lưới nhiều cột, bấm để xem lớn
    (lightbox có chuyển ảnh ←/→). Giữ style tối Eskaylation, responsive mọi thiết bị. */
export function Photos() {
  const state = useLiveApi(() => api.listAll('photos'), [])
  const items: ContentOut[] =
    state.status === 'success' ? state.data.items : EMPTY_ITEMS

  // Trải phẳng mọi media của mọi bài thành một dải ảnh
  const photos = useMemo<Photo[]>(
    () =>
      items.flatMap((c) =>
        c.media.filter((m) => m.mime_type.startsWith('image/') && Boolean(m.url)).map((m) => ({
          id: `${c.id}:${m.url}`,
          url: m.url,
          media: m,
          alt: m.alt_text ?? c.title,
          caption: m.caption,
          postTitle: c.title,
          author: typeof c.body.author === 'string' ? c.body.author : c.title,
          date: c.published_at,
        })),
      ),
    [items],
  )

  const [activeId, setActiveId] = useState<string | null>(null)
  const [visible, setVisible] = useState(PER_PAGE)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const swipeX = useRef<number | null>(null)
  const shown = photos.slice(0, visible)
  const hasMore = visible < photos.length

  const active = photos.findIndex((photo) => photo.id === activeId)
  const cur = active >= 0 ? photos[active] : null

  function go(delta: number) {
    const next = active + delta
    if (next >= 0 && next < photos.length) setActiveId(photos[next].id)
  }

  // `visible` in deps re-observes after each batch; IntersectionObserver won't refire if the sentinel never left view.
  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !hasMore) return
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setVisible((v) => v + PER_PAGE),
      { rootMargin: '600px 0px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [visible, hasMore])

  useEffect(() => {
    if (activeId !== null && active < 0 && state.status === 'success') setActiveId(null)
  }, [activeId, active, state.status])

  useEffect(() => {
    if (active < 0) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      event.preventDefault()
      const next = active + (event.key === 'ArrowLeft' ? -1 : 1)
      if (next >= 0 && next < photos.length) setActiveId(photos[next].id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, photos])

  // The lightbox can step past the rendered grid; grow it so closing lands on that photo.
  useEffect(() => {
    if (active >= visible) setVisible(Math.ceil((active + 1) / PER_PAGE) * PER_PAGE)
  }, [active, visible])

  if (state.status === 'loading') return <div className="photos" aria-busy="true"><h1 className="sr-only">Thư viện ảnh</h1><p role="status">Đang tải ảnh…</p></div>
  if (state.status === 'error') return <div className="photos"><h1 className="sr-only">Thư viện ảnh</h1><EmptyState title="Không tải được ảnh." /></div>
  if (photos.length === 0)
    return <div className="photos"><h1 className="sr-only">Thư viện ảnh</h1><EmptyState title="Hiện tại chưa có ảnh." /></div>


  return (
    <div className="photos">
      <h1 className="sr-only">Thư viện ảnh</h1>
      <div className="photos__grid">
        {shown.map((p, i) => (
          <button
            type="button"
            className="photos__item"
            key={p.id}
            onClick={() => setActiveId(p.id)}
            aria-label={p.caption ?? p.postTitle}
          >
            <MediaImage media={p.media} alt={p.alt} loading={i < 4 ? 'eager' : 'lazy'} />
            <span className="photos__frame" aria-hidden="true" />
            {p.caption && <span className="photos__cap">{p.caption}</span>}
          </button>
        ))}
      </div>

      {hasMore && (
        <div ref={sentinelRef} className="photos__more" role="status">
          Đang tải thêm ảnh…
        </div>
      )}

      {cur && (
        <Modal onClose={() => setActiveId(null)} label="Xem ảnh" variant="bare" showClose>
          <figure
            className="photos__viewer"
            onPointerDown={(e) => { swipeX.current = e.clientX }}
            onPointerUp={(e) => {
              if (swipeX.current === null) return
              const dx = e.clientX - swipeX.current
              swipeX.current = null
              if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1)
            }}
            onPointerCancel={() => { swipeX.current = null }}
          >
            {active > 0 && (
              <button
                type="button"
                className="photos__nav photos__nav--prev"
                onClick={() => go(-1)}
                aria-label="Ảnh trước"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <polyline points="15,4 7,12 15,20" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              </button>
            )}
            <MediaImage key={cur.url} className="photos__viewer-img" media={cur.media} original alt={cur.alt} loading="eager" />
            {active < photos.length - 1 && (
              <button
                type="button"
                className="photos__nav photos__nav--next"
                onClick={() => go(1)}
                aria-label="Ảnh sau"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <polyline points="9,4 17,12 9,20" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              </button>
            )}
            <figcaption className="photos__viewer-meta">
              <span className="photos__viewer-title">
                {cur.caption ?? cur.postTitle}
              </span>
              <span className="photos__viewer-sub">
                {cur.author}
                {cur.date && <> · {fmtDate(cur.date)}</>}
                {' · '}
                {active + 1}/{photos.length}
              </span>
            </figcaption>
          </figure>
        </Modal>
      )}
    </div>
  )
}
