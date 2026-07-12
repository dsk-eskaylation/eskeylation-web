import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { VideoModal } from '../components/VideoModal'
import { EmptyState } from '../components/EmptyState'
import { usePlayer, audioUrl, coverUrl, artistOf } from '../player/PlayerContext'
import { MUSIC_GENRES } from '../genres'
import './Music.css'

/* 'ALL' là mục ảo -> chọn = bỏ lọc (category null). Các thể loại lấy từ hằng
   dùng chung với CMS (MUSIC_GENRES) để đồng bộ. */
const CATEGORIES = ['ALL', ...MUSIC_GENRES]

/* Mảng rỗng ổn định — tránh effect chạy lại vì tạo [] mới mỗi render */
const EMPTY_ITEMS: ContentOut[] = []

/* Góc ngắm trang trí quanh cover (Figma EL-20a8c54a) */
function Brackets({ flip = false }: { flip?: boolean }) {
  return (
    <div className={flip ? 'music__brackets music__brackets--flip' : 'music__brackets'}>
      <span />
      <span />
    </div>
  )
}

/** Trang Nghe nhạc — trải nghiệm phát trực tuyến kiểu Spotify, giữ style Eskaylation:
    thể loại trên cùng, cover lớn "đang phát" + danh sách bài bên phải.
    Bài có body.audio_url -> stream qua trình phát toàn cục (phát nền + màn khoá).
    Bài chưa có audio_url -> mở VideoModal (giữ hành vi cũ với dữ liệu hiện tại). */
export function Music() {
  const [category, setCategory] = useState<string | null>(null)
  const [modal, setModal] = useState<ContentOut | null>(null)
  const player = usePlayer()

  const state = useApi(
    () => api.list('music', { category: category || undefined, pageSize: 60 }),
    [category],
  )
  const items = state.status === 'success' ? state.data.items : EMPTY_ITEMS

  // Bài nổi bật ở hero: bài đang phát nếu thuộc danh sách này, không thì bài đầu
  const playingInList =
    player.current && items.some((i) => i.id === player.current!.id)
      ? player.current
      : null
  const featured = playingInList ?? items[0]

  const isCurrent = (c: ContentOut) => player.current?.id === c.id

  /* Bấm một bài: có audio_url -> phát vào trình phát; chưa có -> mở modal */
  function activate(c: ContentOut) {
    if (audioUrl(c)) {
      const idx = items.findIndex((i) => i.id === c.id)
      if (isCurrent(c)) player.toggle()
      else player.playQueue(items, idx)
    } else {
      setModal(c)
    }
  }

  return (
    <div className="music">
      {/* Thể loại trên cùng */}
      <div className="music__topbar">
        <div className="music__categories">
          {CATEGORIES.map((c) => {
            const isAll = c === 'ALL'
            const active = isAll ? category === null : category === c
            return (
              <button
                key={c}
                type="button"
                className={active ? 'music__cat music__cat--active' : 'music__cat'}
                onClick={() => setCategory(isAll || active ? null : c)}
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
          {/* Hero: cover lớn của bài nổi bật + nút phát chính */}
          <div className="music__hero">
            <Brackets />
            <div className="music__cover" key={featured.id}>
              {coverUrl(featured) ? (
                <img src={coverUrl(featured)!} alt={featured.title} />
              ) : (
                <span className="music__cover-empty" />
              )}
              <button
                type="button"
                className="music__cover-play"
                onClick={() => activate(featured)}
                aria-label={
                  isCurrent(featured) && player.isPlaying
                    ? `Tạm dừng ${featured.title}`
                    : `Phát ${featured.title}`
                }
              >
                {isCurrent(featured) && player.isPlaying ? (
                  <svg viewBox="0 0 24 24">
                    <rect x="6" y="5" width="4" height="14" fill="currentColor" />
                    <rect x="14" y="5" width="4" height="14" fill="currentColor" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24">
                    <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                  </svg>
                )}
              </button>
            </div>
            <Brackets flip />
            <div className="music__hero-meta">
              <h2 className="music__hero-title">{featured.title.toUpperCase()}</h2>
              <svg viewBox="0 0 47 2" className="music__hero-line" aria-hidden="true">
                <line x1="0" y1="1" x2="47" y2="1" stroke="currentColor" />
              </svg>
              <span className="music__hero-artist">{artistOf(featured).toUpperCase()}</span>
            </div>
          </div>

          {/* Danh sách bài — hàng theo kiểu Spotify */}
          <aside className="music__side">
            <div className="music__side-head">
              <span className="music__side-label">Danh sách phát</span>
              <Link to="/music/all" className="music__see-all" title="Xem tất cả và tìm kiếm">
                Xem tất cả
              </Link>
            </div>
            <ol className="music__list">
              {items.map((c, i) => {
                const active = isCurrent(c)
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      className={active ? 'music__row music__row--active' : 'music__row'}
                      onClick={() => activate(c)}
                    >
                      <span className="music__row-idx" aria-hidden="true">
                        {active && player.isPlaying ? (
                          <span className="music__eq">
                            <i />
                            <i />
                            <i />
                          </span>
                        ) : (
                          i + 1
                        )}
                      </span>
                      {coverUrl(c) ? (
                        <img className="music__row-cover" src={coverUrl(c)!} alt="" loading="lazy" />
                      ) : (
                        <span className="music__row-cover music__row-cover--empty" />
                      )}
                      <span className="music__row-meta">
                        <span className="music__row-title">{c.title}</span>
                        <span className="music__row-artist">{artistOf(c)}</span>
                      </span>
                      {!audioUrl(c) && (
                        <span className="music__row-badge" title="Xem dạng video">video</span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ol>
          </aside>
        </section>
      )}

      {modal && <VideoModal content={modal} onClose={() => setModal(null)} />}
    </div>
  )
}
