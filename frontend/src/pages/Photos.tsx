import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Pagination } from '../components/Pagination'
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
  const [params, setParams] = useSearchParams()
  const requestedPage = Number(params.get('page') ?? 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
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
  const topRef = useRef<HTMLDivElement>(null)

  const pageCount = Math.max(1, Math.ceil(photos.length / PER_PAGE))
  // Kẹp page khi số ảnh đổi (vd data mới về)
  const safePage = Math.min(page, pageCount)
  const start = (safePage - 1) * PER_PAGE
  const pagePhotos = photos.slice(start, start + PER_PAGE)

  const active = photos.findIndex((photo) => photo.id === activeId)
  const cur = active >= 0 ? photos[active] : null

  function goPage(nextPage: number) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (nextPage === 1) next.delete('page')
      else next.set('page', String(nextPage))
      return next
    })
    topRef.current?.scrollIntoView({ behavior: 'instant', block: 'start' })
  }

  useEffect(() => {
    if (state.status !== 'success' || page <= pageCount) return
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (pageCount === 1) next.delete('page')
      else next.set('page', String(pageCount))
      return next
    }, { replace: true })
  }, [page, pageCount, state.status, setParams])

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

  if (state.status === 'loading') return <div className="photos" aria-busy="true" />
  if (state.status === 'error') return <EmptyState title="Không tải được ảnh." />
  if (photos.length === 0)
    return <EmptyState title="Hiện tại chưa có ảnh." />


  return (
    <div className="photos">
      <div ref={topRef} className="photos__anchor" aria-hidden="true" />
      {/* key theo trang -> đổi trang thì remount, animation so le chạy lại (mượt) */}
      <div className="photos__grid" key={safePage}>
        {pagePhotos.map((p, i) => (
          <button
            type="button"
            className="photos__item"
            key={p.id}
            style={{ animationDelay: `${(i % PER_PAGE) * 45}ms` }}
            onClick={() => setActiveId(p.id)}
            aria-label={p.caption ?? p.postTitle}
          >
            <MediaImage media={p.media} alt={p.alt} loading={i < 4 ? 'eager' : 'lazy'} />
            <span className="photos__frame" aria-hidden="true" />
            {p.caption && <span className="photos__cap">{p.caption}</span>}
          </button>
        ))}
      </div>

      <Pagination page={safePage} pages={pageCount} label="Phân trang ảnh" onChange={goPage} />

      {cur && (
        <Modal onClose={() => setActiveId(null)} variant="bare" showClose>
          <figure className="photos__viewer">
            {active > 0 && (
              <button
                type="button"
                className="photos__nav photos__nav--prev"
                onClick={() => setActiveId(photos[active - 1].id)}
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
                onClick={() => setActiveId(photos[active + 1].id)}
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
