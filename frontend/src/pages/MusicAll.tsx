import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useDebounced } from '../api/useApi'
import { useLiveApi } from '../api/useLiveApi'
import { useLibraryParams } from '../api/useLibraryParams'
import { Pagination } from '../components/Pagination'
import { LibraryFeedback } from '../components/LibraryFeedback'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { Dropdown } from '../components/Dropdown'
import { AlbumGrid } from '../components/AlbumGrid'
import { albumOptions, SINGLES } from '../albums'
import { MusicCard } from '../components/MusicCard'
import { VideoModal } from '../components/VideoModal'
import { usePlayer, audioUrl, embedUrl } from '../player/PlayerContext'
import './MusicAll.css'

export function MusicAll() {
  const { q, page, setPage, setQuery } = useLibraryParams()
  const debouncedQ = useDebounced(q) // tránh gọi API theo từng phím gõ
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<ContentOut | null>(null)
  const player = usePlayer()
  const [params, setParams] = useSearchParams()
  const album = params.get('album') ?? ''
  const showAlbums = params.get('view') === 'albums'
  const setAlbum = (value: string) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value) next.set('album', value)
        else next.delete('album')
        next.delete('page')
        next.delete('view')
        return next
      },
      { replace: true },
    )
  const setShowAlbums = (value: boolean) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (value) next.set('view', 'albums')
      else next.delete('view')
      return next
    })
  const albums = useLiveApi(() => api.albums(), [])
  // useLiveApi keeps the previous result while refetching; the key tells whether it is current.
  const key = `${album}|${debouncedQ}|${page}`
  const state = useLiveApi(
    () =>
      api
        .list('music', {
          q: debouncedQ || undefined,
          pageSize: 60,
          page,
          album: album && album !== SINGLES ? album : undefined,
          singles: album === SINGLES,
        })
        .then((list) => ({ key, list })),
    [debouncedQ, page, album, attempt],
  )
  const items = state.status === 'success' ? state.data.list.items : []
  const pages = state.status === 'success' ? Math.max(1, state.data.list.pages) : 1
  const busy = state.status === 'success' && state.data.key !== key
  useEffect(() => {
    if (state.status === 'success' && !busy && page > pages) setPage(pages, true)
  }, [state, busy, page, pages, setPage])

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

        <div className="music-all__views" role="group" aria-label="Chế độ xem">
          <button
            type="button"
            className={showAlbums ? 'music-all__view' : 'music-all__view music-all__view--on'}
            aria-pressed={!showAlbums}
            onClick={() => setShowAlbums(false)}
          >
            Bài hát
          </button>
          <button
            type="button"
            className={showAlbums ? 'music-all__view music-all__view--on' : 'music-all__view'}
            aria-pressed={showAlbums}
            onClick={() => setShowAlbums(true)}
          >
            Album
          </button>
        </div>

        {!showAlbums && (
        <div className="music-all__filters">
          <SearchBar
            value={q}
            onChange={setQuery}
            onClear={() => setQuery('')}
          />
          <Dropdown
            label="Lọc theo album"
            value={album}
            onChange={setAlbum}
            options={albumOptions(albums.status === 'success' ? albums.data : [])}
          />
        </div>
        )}
      </header>

      {showAlbums ? (
        <AlbumGrid
          albums={albums.status === 'success' ? albums.data : []}
          onSelect={(slug) => {
            setAlbum(slug)
            window.scrollTo({ top: 0, behavior: 'instant' })
          }}
        />
      ) : (
      <>

      <LibraryFeedback status={state.status} empty={items.length === 0} query={q} noun="bài hát"
        onRetry={() => setAttempt((value) => value + 1)} onClear={() => setQuery('')} />

      <div className="music-all__grid" aria-busy={state.status === 'loading' || busy} inert={busy}>
        {items.map((item, i) => (
          <div
            className="music-all__cell"
            key={item.id}
            style={{ animationDelay: `${(i % 9) * 60}ms` }}
          >
            <MusicCard
              content={item}
              onClick={() =>
                audioUrl(item)
                  ? player.playQueue(items, i)
                  : embedUrl(item)
                    ? player.playEmbed(item)
                    : setSelected(item)
              }
            />
          </div>
        ))}
      </div>

      {state.status === 'success' && <Pagination page={Math.min(page, pages)} pages={pages}
        label="Phân trang nhạc" busy={busy} onChange={(next) => { setPage(next); window.scrollTo({ top: 0, behavior: 'instant' }) }} />}
      </>
      )}

      {selected && (
        <VideoModal content={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
