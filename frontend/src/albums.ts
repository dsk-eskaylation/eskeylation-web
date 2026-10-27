import type { AlbumKind, AlbumOut } from './api/types'
import type { DropdownOption } from './components/Dropdown'

/** Filter value for tracks that belong to no album. */
export const SINGLES = 'bai-le'

export const KIND_LABEL: Record<AlbumKind, string> = {
  album: 'Album',
  mixtape: 'Mixtape',
  ep: 'EP',
  collection: 'Tuyển tập',
}

/** Options for the album filter; counts are omitted when the caller doesn't know them. */
export function albumOptions(albums: AlbumOut[], total?: number, singles?: number): DropdownOption[] {
  return [
    { value: '', label: 'Tất cả bài hát', meta: total === undefined ? undefined : `${total} bài`, image: null },
    ...albums.map((a) => ({
      value: a.slug,
      label: a.title,
      meta: [a.year, `${a.track_count} bài`].filter(Boolean).join(' · '),
      image: a.cover_url,
    })),
    ...(singles === 0
      ? []
      : [{ value: SINGLES, label: 'Bài lẻ', meta: singles === undefined ? undefined : `${singles} bài`, image: null }]),
  ]
}
