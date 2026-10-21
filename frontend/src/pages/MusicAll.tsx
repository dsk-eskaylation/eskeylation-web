import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useDebounced } from '../api/useApi'
import { useLiveApi } from '../api/useLiveApi'
import { useLibraryParams } from '../api/useLibraryParams'
import { Pagination } from '../components/Pagination'
import { LibraryFeedback } from '../components/LibraryFeedback'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { MusicCard } from '../components/MusicCard'
import { VideoModal } from '../components/VideoModal'
import { usePlayer, audioUrl } from '../player/PlayerContext'
import './MusicAll.css'

export function MusicAll() {
  const { q, page, setPage, setQuery } = useLibraryParams()
  const debouncedQ = useDebounced(q) // tránh gọi API theo từng phím gõ
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<ContentOut | null>(null)
  const player = usePlayer()
  const state = useLiveApi(
    () =>
      api.list('music', {
        q: debouncedQ || undefined,
        pageSize: 60,
        page,
      }),
    [debouncedQ, page, attempt],
  )
  const items = state.status === 'success' ? state.data.items : []
  const pages = state.status === 'success' ? Math.max(1, state.data.pages) : 1
  const busy = state.status === 'success' && state.data.page !== page
  useEffect(() => {
    if (state.status === 'success' && state.data.page === page && page > pages) setPage(pages, true)
  }, [state, page, pages, setPage])

  return (
    <div className="music-all">
      <h1 className="page-heading">Thư viện nhạc dạng lưới</h1>
      {/* Header (Figma #1:1385): Quay về | pills | search */}
      <header className="music-all__head">
        <Link to="/music" className="music-all__back">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <polyline
              points="14,5 7,12 14,19"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
          </svg>
          Quay về
        </Link>

        <SearchBar
          value={q}
          onChange={setQuery}
          onClear={() => setQuery('')}
        />
      </header>

      <LibraryFeedback status={state.status} empty={items.length === 0} query={q} noun="bài hát"
        onRetry={() => setAttempt((value) => value + 1)} onClear={() => setQuery('')} />

      <div className="music-all__grid" aria-busy={state.status === 'loading' || busy}>
        {items.map((item, i) => (
          <div
            className="music-all__cell"
            key={item.id}
            style={{ animationDelay: `${(i % 9) * 60}ms` }}
          >
            <MusicCard
              content={item}
              onClick={() =>
                audioUrl(item) ? player.playQueue(items, i) : setSelected(item)
              }
            />
          </div>
        ))}
      </div>

      {state.status === 'success' && <Pagination page={Math.min(page, pages)} pages={pages}
        label="Phân trang nhạc" busy={busy} onChange={(next) => { setPage(next); window.scrollTo({ top: 0, behavior: 'instant' }) }} />}

      {selected && (
        <VideoModal content={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
