import type { AlbumKind } from './api/types'

/** Filter value for tracks that belong to no album. */
export const SINGLES = 'bai-le'

export const KIND_LABEL: Record<AlbumKind, string> = {
  album: 'Album',
  mixtape: 'Mixtape',
  ep: 'EP',
  collection: 'Tuyển tập',
}
