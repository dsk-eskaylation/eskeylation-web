import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import type { ContentOut, MediaOut } from '../api/types'
import { MediaImage } from '../components/MediaImage'
import { Modal } from '../components/Modal'
import { EmptyState } from '../components/EmptyState'
import { useScrollPreload } from '../utils/useScrollPreload'
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

const BATCH = 24

/* Bề rộng cột tối thiểu/gap — khớp breakpoint trong Photos.css */
function columnSpec(width: number) {
  if (width <= 640) return { min: 150, gap: 10 }
  if (width <= 1100) return { min: 220, gap: 14 }
  return { min: 260, gap: 16 }
}

/** Masonry kiểu Pinterest: mỗi ảnh vào cột đang thấp nhất, theo thứ tự.
    Thêm ảnh mới chỉ nối vào cuối cột, ảnh đã hiện không bị xếp lại. */
function toColumns<T extends { media: MediaOut }>(list: T[], count: number) {
  const cols: T[][] = Array.from({ length: count }, () => [])
  const heights = new Array<number>(count).fill(0)
  for (const item of list) {
    const { width, height } = item.media
    const target = heights.indexOf(Math.min(...heights))
    cols[target].push(item)
    heights[target] += width && height ? height / width : 1
  }
  return cols
}

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
  const swipeX = useRef<number | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(BATCH)
  const [columnCount, setColumnCount] = useState(1)
  const shown = useMemo(() => photos.slice(0, visible), [photos, visible])
  const columns = useMemo(() => toColumns(shown, columnCount), [shown, columnCount])
  const hasMore = visible < photos.length

  const active = photos.findIndex((photo) => photo.id === activeId)
  const cur = active >= 0 ? photos[active] : null

  function go(delta: number) {
    const next = active + delta
    if (next >= 0 && next < photos.length) setActiveId(photos[next].id)
  }

  // Số cột theo bề rộng thật của lưới
  const hasGrid = photos.length > 0
  useEffect(() => {
    const grid = gridRef.current
    if (!grid) return
    const observer = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width
      const { min, gap } = columnSpec(window.innerWidth)
      setColumnCount(Math.max(1, Math.floor((width + gap) / (min + gap))))
    })
    observer.observe(grid)
    return () => observer.disconnect()
  }, [hasGrid])

  useScrollPreload(() => setVisible((count) => count + BATCH), hasMore, visible)

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

  if (state.status === 'loading') return <div className="photos" aria-busy="true"><h1 className="sr-only">Thư viện ảnh</h1><p role="status">Đang tải ảnh…</p></div>
  if (state.status === 'error') return <div className="photos"><h1 className="sr-only">Thư viện ảnh</h1><EmptyState title="Không tải được ảnh." /></div>
  if (photos.length === 0)
    return <div className="photos"><h1 className="sr-only">Thư viện ảnh</h1><EmptyState title="Hiện tại chưa có ảnh." /></div>


  return (
    <div className="photos">
      <h1 className="sr-only">Thư viện ảnh</h1>
      <div ref={gridRef} className="photos__grid" aria-busy={hasMore}>
        {columns.map((column, c) => (
          <div className="photos__col" key={c}>
            {column.map((p) => (
              <button
                type="button"
                className="photos__item"
                key={p.id}
                onClick={() => setActiveId(p.id)}
                aria-label={p.caption ?? p.postTitle}
              >
                <MediaImage media={p.media} alt={p.alt} loading={photos.slice(0, 4).includes(p) ? 'eager' : 'lazy'} />
                <span className="photos__frame" aria-hidden="true" />
                {p.caption && <span className="photos__cap">{p.caption}</span>}
              </button>
            ))}
          </div>
        ))}
      </div>

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
