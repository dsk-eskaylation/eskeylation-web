import type { AlbumKind, AlbumOut } from '../api/types'
import './AlbumShelf.css'

export const SINGLES = 'bai-le'

export const KIND_LABEL: Record<AlbumKind, string> = {
  album: 'Album',
  mixtape: 'Mixtape',
  ep: 'EP',
  collection: 'Tuyển tập',
}

interface Props {
  albums: AlbumOut[]
  singles: number
  selected: string | null
  onSelect: (slug: string | null) => void
}

function Card({
  title,
  meta,
  cover,
  active,
  onClick,
}: {
  title: string
  meta: string
  cover: string | null
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={active ? 'album-shelf__card album-shelf__card--active' : 'album-shelf__card'}
      onClick={onClick}
      aria-pressed={active}
    >
      {cover ? (
        <img className="album-shelf__cover" src={cover} alt="" loading="lazy" />
      ) : (
        <span className="album-shelf__cover album-shelf__cover--empty" aria-hidden="true">
          {title.slice(0, 2)}
        </span>
      )}
      <span className="album-shelf__title">{title}</span>
      <span className="album-shelf__meta">{meta}</span>
    </button>
  )
}

export function AlbumShelf({ albums, singles, selected, onSelect }: Props) {
  if (albums.length === 0) return null
  return (
    <nav className="album-shelf" aria-label="Album">
      {albums.map((album) => (
        <Card
          key={album.slug}
          title={album.title}
          meta={[KIND_LABEL[album.kind], album.year, `${album.track_count} bài`]
            .filter(Boolean)
            .join(' · ')}
          cover={album.cover_url}
          active={selected === album.slug}
          onClick={() => onSelect(selected === album.slug ? null : album.slug)}
        />
      ))}
      {singles > 0 && (
        <Card
          title="Bài lẻ"
          meta={`Chưa thuộc album · ${singles} bài`}
          cover={null}
          active={selected === SINGLES}
          onClick={() => onSelect(selected === SINGLES ? null : SINGLES)}
        />
      )}
    </nav>
  )
}
