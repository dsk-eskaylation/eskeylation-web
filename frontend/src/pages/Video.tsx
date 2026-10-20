import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import type { ContentOut } from '../api/types'
import { VideoPlayer } from '../components/VideoPlayer'
import { EmptyState } from '../components/EmptyState'
import './Video.css'

function poster(c: ContentOut) {
  const images = c.media.filter((m) => m.url && (m.mime_type.startsWith('image/') || m.preview_url))
  return images.find((m) => m.is_primary) ?? images[0]
}
function artistOf(c: ContentOut) {
  return typeof c.body.artist === 'string' ? c.body.artist : 'DSK'
}

function VideoThumb({
  content,
  active,
  onClick,
}: {
  content: ContentOut
  active: boolean
  onClick: () => void
}) {
  const media = poster(content)
  return (
    <button
      type="button"
      className={active ? 'video-card video-card--active' : 'video-card'}
      onClick={onClick}
    >
      <div className="video-card__thumb">
        {media?.url ? (
          <img src={media.url} alt={media.alt_text ?? content.title} loading="lazy" />
        ) : (
          <span className="video-card__placeholder" />
        )}
        <span className="video-card__play" aria-hidden="true">
          {active ? (
            <span className="video-card__eq">
              <i />
              <i />
              <i />
            </span>
          ) : (
            <svg viewBox="0 0 24 24">
              <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
            </svg>
          )}
        </span>
      </div>
      <div className="video-card__meta">
        <span className="video-card__title">{content.title}</span>
        <span className="video-card__artist">{artistOf(content)}</span>
      </div>
    </button>
  )
}

/** Trang Video thuần — xem video NGAY TRÊN TRANG (không mở modal):
    player lớn phát inline tại chỗ + lưới video làm playlist. Bấm một video
    -> nạp vào player và phát ngay; điều khiển start/pause trong chính player. */
export function Video() {
  const state = useLiveApi(() => api.listAll('video'), [])
  const items = state.status === 'success' ? state.data.items : []
  const [params] = useSearchParams()
  const requestedId = params.get('v')

  const [currentId, setCurrentId] = useState<number | null>(null)
  const [playingId, setPlayingId] = useState<number | null>(null)
  const heroRef = useRef<HTMLDivElement>(null)
  const requestedVideoId = items.find((x) => String(x.id) === requestedId)?.id

  // Đến từ trang "Xem tất cả" (?v=id) -> nạp đúng video đó vào player & phát
  useEffect(() => {
    if (requestedVideoId === undefined) return
    setCurrentId(requestedVideoId)
    setPlayingId(requestedVideoId)
  }, [requestedVideoId])

  const selected = items.find((x) => x.id === currentId)
  const active = selected ?? items[0]
  const playing = active !== undefined && playingId === active.id
  const selectionRemoved = state.status === 'success' && currentId !== null && !selected
  useEffect(() => {
    if (selectionRemoved) {
      setCurrentId(null)
      setPlayingId(null)
    }
  }, [selectionRemoved])

  function selectVideo(v: ContentOut) {
    setCurrentId(v.id)
    setPlayingId(v.id)
    heroRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="video-page">
      {state.status === 'error' && <EmptyState title="Không tải được video." />}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Hiện tại chưa có video nào TT.  " />
      )}

      {active && (
        <section className="video-hero" ref={heroRef}>
          <div className="video-hero__stage">
            {playing ? (
              // key theo id -> đổi video thì iframe/video nạp lại & phát bài mới
              <VideoPlayer key={active.id} content={active} />
            ) : (
              <button
                type="button"
                className="video-hero__poster"
                onClick={() => {
                  setCurrentId(active.id)
                  setPlayingId(active.id)
                }}
                aria-label={`Phát ${active.title}`}
              >
                {poster(active)?.url ? (
                  <img src={poster(active)!.url} alt={active.title} />
                ) : (
                  <span className="video-card__placeholder" />
                )}
                <span className="video-hero__play" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                  </svg>
                </span>
              </button>
            )}
          </div>
          <div className="video-hero__meta">
            <h1 className="video-hero__title">{active.title}</h1>
            <span className="video-hero__artist">{artistOf(active)}</span>
            {active.summary && (
              <p className="video-hero__summary">{active.summary}</p>
            )}
          </div>
        </section>
      )}

      {items.length > 0 && (
        <div className="video-list">
          <div className="video-list__head">
            <span className="video-list__label">Danh sách video</span>
            <Link to="/video/all" className="video-list__all" title="Xem toàn bộ kho video">
              Xem tất cả
            </Link>
          </div>
          {/* Strip cuộn ngang: lướt sang phải để hiện các video phía sau */}
          <div className="video-strip" aria-label="Danh sách video">
            {items.map((item) => (
              <div className="video-strip__cell" key={item.id}>
                <VideoThumb
                  content={item}
                  active={item.id === active?.id && playing}
                  onClick={() => selectVideo(item)}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
