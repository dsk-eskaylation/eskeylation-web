import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { Modal } from '../components/Modal'
import { EmptyState } from '../components/EmptyState'
import './Photos.css'

interface Photo {
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

/* Danh sách số trang hiển thị: rút gọn bằng '…' khi nhiều trang
   (vd 1 … 4 5 6 … 12). Trả về số trang (1-index) hoặc null = dấu '…'. */
function pageList(current: number, total: number): (number | null)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const out: (number | null)[] = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  if (start > 2) out.push(null)
  for (let p = start; p <= end; p++) out.push(p)
  if (end < total - 1) out.push(null)
  out.push(total)
  return out
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
  const state = useApi(() => api.list('photos', { pageSize: 60 }), [])
  const items: ContentOut[] =
    state.status === 'success' ? state.data.items : EMPTY_ITEMS

  // Trải phẳng mọi media của mọi bài thành một dải ảnh
  const photos = useMemo<Photo[]>(
    () =>
      items.flatMap((c) =>
        c.media.map((m) => ({
          url: m.url,
          alt: m.alt_text ?? c.title,
          caption: m.caption,
          postTitle: c.title,
          author: typeof c.body.author === 'string' ? c.body.author : c.title,
          date: c.published_at,
        })),
      ),
    [items],
  )

  const [active, setActive] = useState<number | null>(null)
  const [page, setPage] = useState(0) // 0-index
  const topRef = useRef<HTMLDivElement>(null)

  const pageCount = Math.max(1, Math.ceil(photos.length / PER_PAGE))
  // Kẹp page khi số ảnh đổi (vd data mới về)
  const safePage = Math.min(page, pageCount - 1)
  const start = safePage * PER_PAGE
  const pagePhotos = photos.slice(start, start + PER_PAGE)

  function goPage(p: number) {
    setPage(p)
    // Cuộn mượt về đầu thư viện để thấy trang mới từ đầu
    topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  useEffect(() => {
    if (active === null) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') setActive((i) => (i === null ? i : Math.max(0, i - 1)))
      if (e.key === 'ArrowRight')
        setActive((i) => (i === null ? i : Math.min(photos.length - 1, i + 1)))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, photos.length])

  if (state.status === 'loading') return <div className="photos" aria-busy="true" />
  if (state.status === 'error') return <EmptyState title="Không tải được ảnh." />
  if (photos.length === 0)
    return <EmptyState title="Hiện tại chưa có ảnh nào TT.  " />

  const cur = active !== null ? photos[active] : null

  return (
    <div className="photos">
      <div ref={topRef} className="photos__anchor" aria-hidden="true" />
      {/* key theo trang -> đổi trang thì remount, animation so le chạy lại (mượt) */}
      <div className="photos__grid" key={safePage}>
        {pagePhotos.map((p, i) => (
          <button
            type="button"
            className="photos__item"
            key={`${p.url}-${i}`}
            style={{ animationDelay: `${(i % PER_PAGE) * 45}ms` }}
            onClick={() => setActive(start + i)}
            aria-label={p.caption ?? p.postTitle}
          >
            <img src={p.url} alt={p.alt} loading="lazy" />
            <span className="photos__frame" aria-hidden="true" />
            {p.caption && <span className="photos__cap">{p.caption}</span>}
          </button>
        ))}
      </div>

      {pageCount > 1 && (
        <nav className="photos__pager" aria-label="Phân trang ảnh">
          <button
            type="button"
            className="photos__pager-arrow"
            onClick={() => goPage(Math.max(0, safePage - 1))}
            disabled={safePage === 0}
            aria-label="Trang trước"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <polyline points="15,4 7,12 15,20" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>

          {pageList(safePage + 1, pageCount).map((p, i) =>
            p === null ? (
              <span key={`gap-${i}`} className="photos__pager-gap">…</span>
            ) : (
              <button
                key={p}
                type="button"
                className={
                  p === safePage + 1
                    ? 'photos__pager-num photos__pager-num--active'
                    : 'photos__pager-num'
                }
                onClick={() => goPage(p - 1)}
                aria-current={p === safePage + 1 ? 'page' : undefined}
              >
                {p}
              </button>
            ),
          )}

          <button
            type="button"
            className="photos__pager-arrow"
            onClick={() => goPage(Math.min(pageCount - 1, safePage + 1))}
            disabled={safePage === pageCount - 1}
            aria-label="Trang sau"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <polyline points="9,4 17,12 9,20" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
        </nav>
      )}

      {cur && (
        <Modal onClose={() => setActive(null)} variant="bare" showClose>
          <figure className="photos__viewer">
            {active !== null && active > 0 && (
              <button
                type="button"
                className="photos__nav photos__nav--prev"
                onClick={() => setActive((i) => (i === null ? i : i - 1))}
                aria-label="Ảnh trước"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <polyline points="15,4 7,12 15,20" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              </button>
            )}
            <img className="photos__viewer-img" src={cur.url} alt={cur.alt} />
            {active !== null && active < photos.length - 1 && (
              <button
                type="button"
                className="photos__nav photos__nav--next"
                onClick={() => setActive((i) => (i === null ? i : i + 1))}
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
                {(active ?? 0) + 1}/{photos.length}
              </span>
            </figcaption>
          </figure>
        </Modal>
      )}
    </div>
  )
}
