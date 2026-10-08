import type { ContentOut } from '../api/types'
import './MusicCard.css'

function primary(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}

function timeParts(iso: string | null) {
  if (!iso) return { time: '', date: '' }
  const d = new Date(iso)
  return {
    time: `${d.getHours()}g${String(d.getMinutes()).padStart(2, '0')}`,
    date: `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`,
  }
}

/** Card nhạc trang "Xem tất cả" (Figma EL-3ff63958):
    meta 2 hàng (title/artist + giờ/ngày) rồi thumbnail có góc ngắm + nút play. */
export function MusicCard({
  content,
  onClick,
}: {
  content: ContentOut
  onClick?: () => void
}) {
  const artist = typeof content.body.artist === 'string' ? content.body.artist : 'DSK'
  const { time, date } = timeParts(content.published_at)
  const media = primary(content)

  return (
    <button type="button" className="music-card" onClick={onClick}>
      <div className="music-card__meta">
        <div className="music-card__row music-card__row--title">
          <span>{content.title.toUpperCase()}</span>
          <span>{artist.toUpperCase()}</span>
        </div>
        <div className="music-card__row music-card__row--sub">
          <span>{time}</span>
          <span>{date}</span>
        </div>
      </div>

      <div className="music-card__frame">
        <span className="music-card__corner music-card__corner--tl" />
        <span className="music-card__corner music-card__corner--tr" />
        <span className="music-card__corner music-card__corner--bl" />
        <span className="music-card__corner music-card__corner--br" />
        <div className="music-card__thumb">
          {media ? (
            <img src={media.url} alt={media.alt_text ?? content.title} loading="lazy" />
          ) : (
            <span className="music-card__placeholder" />
          )}
          <span className="music-card__play" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
            </svg>
          </span>
        </div>
      </div>
    </button>
  )
}
