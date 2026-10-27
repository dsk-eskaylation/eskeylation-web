import type { AlbumOut } from '../api/types'
import { KIND_LABEL, SINGLES } from '../albums'
import './AlbumGrid.css'

function Cover({ src }: { src: string | null }) {
  return src ? (
    <img className="album-grid__cover" src={src} alt="" loading="lazy" />
  ) : (
    <span className="album-grid__cover album-grid__cover--empty" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d="M9 18V5l11-2v13" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx="6" cy="18" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="17" cy="16" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </span>
  )
}

export function AlbumGrid({ albums, onSelect }: { albums: AlbumOut[]; onSelect: (slug: string) => void }) {
  return (
    <ul className="album-grid">
      {albums.map((album) => (
        <li key={album.slug}>
          <button type="button" className="album-grid__card" onClick={() => onSelect(album.slug)}>
            <Cover src={album.cover_url} />
            <span className="album-grid__title">{album.title}</span>
            <span className="album-grid__meta">
              {[KIND_LABEL[album.kind], album.year, `${album.track_count} bài`].filter(Boolean).join(' · ')}
            </span>
          </button>
        </li>
      ))}
      <li>
        <button type="button" className="album-grid__card" onClick={() => onSelect(SINGLES)}>
          <Cover src={null} />
          <span className="album-grid__title">Bài lẻ</span>
          <span className="album-grid__meta">Chưa thuộc album</span>
        </button>
      </li>
    </ul>
  )
}
