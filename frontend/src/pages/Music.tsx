import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { VideoModal } from '../components/VideoModal'
import { EmptyState } from '../components/EmptyState'
import './Music.css'

const CATEGORIES = ['LIFE RAP', 'LOVE RAP', 'GANGSTA', "DISSIN'", 'AI']

function primaryMedia(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}

/** Debounce giá trị search cho mượt (gõ xong 300ms mới gọi API). */
function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

/* Góc ngắm trang trí quanh player (Figma EL-20a8c54a: 12x12, nét trên+trái) */
function Brackets({ flip = false }: { flip?: boolean }) {
  return (
    <div className={flip ? 'music__brackets music__brackets--flip' : 'music__brackets'}>
      <span />
      <span />
    </div>
  )
}

export function Music() {
  const [q, setQ] = useState('')
  const debouncedQ = useDebounced(q)
  const [category, setCategory] = useState<string | null>(null)
  const [featuredId, setFeaturedId] = useState<number | null>(null)
  const [playing, setPlaying] = useState<ContentOut | null>(null)

  const state = useApi(
    () =>
      api.list('music', {
        q: debouncedQ || undefined,
        category: category || undefined,
      }),
    [debouncedQ, category],
  )

  const items = state.status === 'success' ? state.data.items : []
  const featured = items.find((i) => i.id === featuredId) ?? items[0]
  const searching = q.trim().length > 0
  const noResult = searching && state.status === 'success' && items.length === 0

  const pick = (item: ContentOut) => {
    setFeaturedId(item.id)
    setQ('')
  }

  /* Playlist dọc quanh bài đang chọn (Figma #1:570: 5 thumb, giữa nổi bật) */
  const fIdx = featured ? items.indexOf(featured) : 0
  const around = items.length
    ? [-2, -1, 0, 1, 2].map((d) => items[(fIdx + d + items.length) % items.length])
    : []

  const artist = (c: ContentOut) =>
    typeof c.body.artist === 'string' ? c.body.artist : 'DSK'

  return (
    <div className="music">
      <div className="music__topbar">
        <div className="music__search">
          <SearchBar
            value={q}
            onChange={setQ}
            placeholder="Tìm kiếm bài hát"
            error={noResult}
            onClear={() => setQ('')}
          />
          {/* Dropdown gợi ý (Figma #1:758) */}
          {searching && items.length > 0 && (
            <ul className="music__suggest" role="listbox">
              {items.slice(0, 4).map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => pick(item)}>
                    {item.title}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {/* Báo lỗi tìm kiếm (Figma #1:972) */}
          {noResult && (
            <p className="music__search-error">
              <span>*</span>Hiện tại chưa có bài hát này. Bạn hãy thử lại
            </p>
          )}
        </div>

        <div className="music__categories">
          {CATEGORIES.map((c) => {
            const active = category === c
            return (
              <button
                key={c}
                type="button"
                className={active ? 'music__cat music__cat--active' : 'music__cat'}
                onClick={() => setCategory(active ? null : c)}
              >
                <svg viewBox="0 0 27 2" className="music__cat-line" aria-hidden="true">
                  <line x1="0" y1="1" x2="27" y2="1" stroke="currentColor" />
                </svg>
                {c}
              </button>
            )
          })}
        </div>
      </div>

      {state.status === 'error' && <EmptyState title="Không tải được nhạc." />}
      {state.status === 'success' && items.length === 0 && !searching && (
        <EmptyState title="Hiện tại chưa có bài hát nào TT.  " />
      )}

      {featured && (
        <section
          className={searching ? 'music__stage music__stage--dim' : 'music__stage'}
        >
          {/* Tiêu đề bài + gạch ngang (Figma #1:554) */}
          <div className="music__head" key={featured.id}>
            <h2 className="music__title">
              {featured.title.toUpperCase()} - {artist(featured).toUpperCase()}
            </h2>
            <svg viewBox="0 0 47 2" className="music__head-line" aria-hidden="true">
              <line x1="0" y1="1" x2="47" y2="1" stroke="currentColor" />
            </svg>
          </div>

          {/* Player giữa với góc ngắm (Figma #1:557) */}
          <div className="music__player-wrap">
            <Brackets />
            <button
              type="button"
              className="music__player"
              onClick={() => setPlaying(featured)}
              aria-label={`Phát ${featured.title}`}
            >
              {primaryMedia(featured) ? (
                <img
                  key={featured.id}
                  src={primaryMedia(featured)!.url}
                  alt={featured.title}
                />
              ) : (
                <span className="music__player-empty" />
              )}
              <span className="music__player-play" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                </svg>
              </span>
            </button>
            <Brackets flip />
          </div>

          {/* Cột phải: Xem tất cả + playlist dọc (Figma #1:565) */}
          <aside className="music__side">
            <Link to="/music/all" className="music__see-all">
              Xem tất cả
            </Link>
            <div className="music__side-row">
              <svg viewBox="0 0 47 2" className="music__side-line" aria-hidden="true">
                <line x1="0" y1="1" x2="47" y2="1" stroke="currentColor" />
              </svg>
              {around.length > 1 && (
                <div className="music__playlist" aria-label="Danh sách phát">
                  {around.map((item, i) => (
                    <button
                      key={`${item.id}-${i}`}
                      type="button"
                      className={
                        i === 2 ? 'music__thumb music__thumb--active' : 'music__thumb'
                      }
                      onClick={() => (i === 2 ? setPlaying(item) : pick(item))}
                      aria-label={item.title}
                    >
                      {primaryMedia(item) && (
                        <img src={primaryMedia(item)!.url} alt="" loading="lazy" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </section>
      )}

      {playing && <VideoModal content={playing} onClose={() => setPlaying(null)} />}
    </div>
  )
}
