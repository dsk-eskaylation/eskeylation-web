import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useDebounced } from '../api/useApi'
import { useLiveApi } from '../api/useLiveApi'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { EmptyState } from '../components/EmptyState'
import './Video.css'

function poster(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}
function artistOf(c: ContentOut) {
  return typeof c.body.artist === 'string' ? c.body.artist : 'DSK'
}

/** Trang Xem tất cả video — toàn bộ kho, có tìm kiếm. Bấm một video sẽ về
    /video và phát ngay trên trang (qua ?v=id). */
export function VideoAll() {
  const [q, setQ] = useState('')
  const debouncedQ = useDebounced(q)
  const [page, setPage] = useState(1)
  const navigate = useNavigate()
  const state = useLiveApi(
    () => api.list('video', { q: debouncedQ || undefined, pageSize: 60, page }),
    [debouncedQ, page],
  )
  const items = state.status === 'success' ? state.data.items : []

  return (
    <div className="video-all">
      <header className="video-all__head">
        <Link to="/video" className="video-all__back">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <polyline points="14,5 7,12 14,19" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
          Quay về
        </Link>
        <SearchBar value={q} placeholder="Tìm kiếm video" onChange={(value) => { setQ(value); setPage(1) }} onClear={() => { setQ(''); setPage(1) }} />
      </header>

      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Không tìm thấy video nào TT.  " />
      )}

      <div className="video-grid">
        {items.map((item, i) => {
          const media = poster(item)
          return (
            <div
              className="video-grid__cell"
              key={item.id}
              style={{ animationDelay: `${(i % 9) * 50}ms` }}
            >
              <button
                type="button"
                className="video-card"
                onClick={() => navigate(`/video?v=${item.id}`)}
              >
                <div className="video-card__thumb">
                  {media?.url ? (
                    <img src={media.url} alt={media.alt_text ?? item.title} loading="lazy" />
                  ) : (
                    <span className="video-card__placeholder" />
                  )}
                  <span className="video-card__play" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                    </svg>
                  </span>
                </div>
                <div className="video-card__meta">
                  <span className="video-card__title">{item.title}</span>
                  <span className="video-card__artist">{artistOf(item)}</span>
                </div>
              </button>
            </div>
          )
        })}
      </div>

      {state.status === 'success' && state.data.pages > 1 && (
        <nav aria-label="Phân trang video">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trang trước</button>
          <span> {page} / {state.data.pages} </span>
          <button type="button" disabled={page >= state.data.pages} onClick={() => setPage(page + 1)}>Trang sau</button>
        </nav>
      )}
    </div>
  )
}
