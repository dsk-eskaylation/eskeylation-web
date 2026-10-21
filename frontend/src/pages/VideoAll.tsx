import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useDebounced } from '../api/useApi'
import { useLiveApi } from '../api/useLiveApi'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { LibraryFeedback } from '../components/LibraryFeedback'
import { Pagination } from '../components/Pagination'
import { useLibraryParams } from '../api/useLibraryParams'
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
  const { q, page, setPage, setQuery } = useLibraryParams()
  const debouncedQ = useDebounced(q)
  const [attempt, setAttempt] = useState(0)
  const navigate = useNavigate()
  const state = useLiveApi(
    () => api.list('video', { q: debouncedQ || undefined, pageSize: 60, page }),
    [debouncedQ, page, attempt],
  )
  const items = state.status === 'success' ? state.data.items : []
  const pages = state.status === 'success' ? Math.max(1, state.data.pages) : 1
  const busy = state.status === 'success' && state.data.page !== page
  useEffect(() => {
    if (state.status === 'success' && state.data.page === page && page > pages) setPage(pages, true)
  }, [state, page, pages, setPage])

  return (
    <div className="video-all">
      <h1 className="page-heading">Thư viện video</h1>
      <header className="video-all__head">
        <Link to="/video" className="video-all__back">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <polyline points="14,5 7,12 14,19" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
          Quay về
        </Link>
        <SearchBar value={q} placeholder="Tìm kiếm video" onChange={setQuery} onClear={() => setQuery('')} />
      </header>

      <LibraryFeedback status={state.status} empty={items.length === 0} query={q} noun="video"
        onRetry={() => setAttempt((value) => value + 1)} onClear={() => setQuery('')} />

      <div className="video-grid" aria-busy={state.status === 'loading' || busy}>
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

      {state.status === 'success' && <Pagination page={Math.min(page, pages)} pages={pages}
        label="Phân trang video" busy={busy} onChange={(next) => { setPage(next); window.scrollTo({ top: 0, behavior: 'instant' }) }} />}
    </div>
  )
}
