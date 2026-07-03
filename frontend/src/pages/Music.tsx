import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { VideoModal } from '../components/VideoModal'
import { EmptyState } from '../components/EmptyState'
import './Music.css'

const CATEGORIES = ['LIFE RAP', 'LOVE RAP', 'GANGSTA', "DISSIN'", 'AI']

/* Mảng rỗng ổn định — tránh effect chạy lại vì tạo [] mới mỗi render */
const EMPTY_ITEMS: ContentOut[] = []

function primaryMedia(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
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

/** Trang Nghe nhạc (Figma #1:373) — trải nghiệm "đang phát":
    thể loại ở giữa phía trên, sân khấu 3 cột (tên bài | player | playlist).
    KHÔNG có search ở đây — muốn tìm bài, user bấm "Xem tất cả" (theo design).
    Điều hướng nhanh: phím ↑/↓ hoặc click thumb để đổi bài, Enter/click player để phát. */
export function Music() {
  const [category, setCategory] = useState<string | null>(null)
  const [featuredId, setFeaturedId] = useState<number | null>(null)
  const [playing, setPlaying] = useState<ContentOut | null>(null)

  const state = useApi(
    () => api.list('music', { category: category || undefined }),
    [category],
  )

  const items = state.status === 'success' ? state.data.items : EMPTY_ITEMS
  const foundIdx =
    featuredId === null ? -1 : items.findIndex((i) => i.id === featuredId)
  const fIdx = foundIdx === -1 ? 0 : foundIdx
  const featured: ContentOut | undefined = items[fIdx]
  const featuredMedia = featured ? primaryMedia(featured) : undefined

  /* Đặt mình vào người nghe: đứng ở player, ↑/↓ lướt bài như đổi kênh */
  useEffect(() => {
    if (playing || items.length < 2) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
      e.preventDefault()
      const dir = e.key === 'ArrowDown' ? 1 : -1
      const next = items[(fIdx + dir + items.length) % items.length]
      setFeaturedId(next.id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [items, fIdx, playing])

  /* Playlist dọc quanh bài đang chọn (Figma #1:570: 5 thumb, giữa nổi bật) */
  const around = items.length
    ? [-2, -1, 0, 1, 2].map((d) => items[(fIdx + d + items.length) % items.length])
    : []

  const artist = (c: ContentOut) =>
    typeof c.body.artist === 'string' ? c.body.artist : 'DSK'

  return (
    <div className="music">
      {/* Thể loại ở GIỮA phía trên player (Figma #1:536: cột 183 tại trung tâm) */}
      <div className="music__topbar">
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
                {c}
                <svg viewBox="0 0 27 2" className="music__cat-line" aria-hidden="true">
                  <line x1="0" y1="1" x2="27" y2="1" stroke="currentColor" />
                </svg>
              </button>
            )
          })}
        </div>
      </div>

      {state.status === 'error' && <EmptyState title="Không tải được nhạc." />}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Hiện tại chưa có bài hát nào TT.  " />
      )}

      {featured && (
        <section className="music__stage">
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
              {featuredMedia ? (
                <img key={featured.id} src={featuredMedia.url} alt={featured.title} />
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

          {/* Cột phải: Xem tất cả (nơi có tìm kiếm) + playlist dọc (Figma #1:565) */}
          <aside className="music__side">
            <Link
              to="/music/all"
              className="music__see-all"
              title="Xem toàn bộ và tìm kiếm bài hát"
            >
              Xem tất cả
            </Link>
            <div className="music__side-row">
              <svg viewBox="0 0 47 2" className="music__side-line" aria-hidden="true">
                <line x1="0" y1="1" x2="47" y2="1" stroke="currentColor" />
              </svg>
              {around.length > 1 && (
                <div className="music__playlist" aria-label="Danh sách phát">
                  {around.map((item, i) => {
                    const media = primaryMedia(item)
                    return (
                      <button
                        key={`${item.id}-${i}`}
                        type="button"
                        className={
                          i === 2 ? 'music__thumb music__thumb--active' : 'music__thumb'
                        }
                        onClick={() =>
                          i === 2 ? setPlaying(item) : setFeaturedId(item.id)
                        }
                        aria-label={item.title}
                      >
                        {media && <img src={media.url} alt="" loading="lazy" />}
                      </button>
                    )
                  })}
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
