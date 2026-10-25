import type { AlbumOut } from '../api/types'
import { KIND_LABEL, SINGLES } from '../albums'
import { Modal } from './Modal'
import './AlbumBrowser.css'

interface Props {
  albums: AlbumOut[]
  singles: number
  selected: string | null
  onSelect: (slug: string | null) => void
  onClose: () => void
}

function Card({ title, meta, cover, active, onClick }: {
  title: string
  meta: string
  cover: string | null
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={active ? 'album-browser__card album-browser__card--active' : 'album-browser__card'}
      onClick={onClick}
      aria-pressed={active}
    >
      {cover ? (
        <img className="album-browser__cover" src={cover} alt="" loading="lazy" />
      ) : (
        <span className="album-browser__cover album-browser__cover--empty" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M9 18V5l11-2v13" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <circle cx="6" cy="18" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="17" cy="16" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </span>
      )}
      <span className="album-browser__title">{title}</span>
      <span className="album-browser__meta">{meta}</span>
    </button>
  )
}

export function AlbumBrowser({ albums, singles, selected, onSelect, onClose }: Props) {
  const pick = (slug: string | null) => {
    onSelect(slug)
    onClose()
  }
  return (
    <Modal onClose={onClose} variant="full" showClose={false} label="Tất cả album">
      <div className="album-browser">
        <div className="album-browser__inner">
          <header className="album-browser__head">
            <h2>Tất cả album</h2>
            <button type="button" className="album-browser__close" onClick={onClose} aria-label="Đóng">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </header>
          <div className="album-browser__grid">
            <Card
              title="Tất cả bài hát"
              meta="Toàn bộ thư viện"
              cover={null}
              active={!selected}
              onClick={() => pick(null)}
            />
            {albums.map((album) => (
              <Card
                key={album.slug}
                title={album.title}
                meta={[KIND_LABEL[album.kind], album.year, `${album.track_count} bài`].filter(Boolean).join(' · ')}
                cover={album.cover_url}
                active={selected === album.slug}
                onClick={() => pick(album.slug)}
              />
            ))}
            {singles > 0 && (
              <Card
                title="Bài lẻ"
                meta={`Chưa thuộc album · ${singles} bài`}
                cover={null}
                active={selected === SINGLES}
                onClick={() => pick(SINGLES)}
              />
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
