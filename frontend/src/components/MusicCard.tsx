import type { ContentOut } from '../api/types'
import { MediaFrame } from './MediaFrame'
import './MusicCard.css'

function primary(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}

/** Card nhạc: thumbnail + title + artist. Click để mở video. */
export function MusicCard({
  content,
  onClick,
}: {
  content: ContentOut
  onClick?: () => void
}) {
  const artist = typeof content.body.artist === 'string' ? content.body.artist : null
  return (
    <button type="button" className="music-card" onClick={onClick}>
      <MediaFrame media={primary(content)} ratio="431 / 237" />
      <div className="music-card__meta">
        <span className="music-card__title">{content.title}</span>
        {artist && <span className="muted">{artist}</span>}
      </div>
    </button>
  )
}
