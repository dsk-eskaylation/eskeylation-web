export type ContentType = 'music' | 'gallery' | 'community' | 'homepage' | 'video'

export interface MediaOut {
  media_id?: number | null
  url: string
  preview_url?: string | null
  stream_url?: string | null
  original_url?: string | null
  srcset?: string | null
  caption: string | null
  alt_text: string | null
  is_primary: boolean
  width: number | null
  height: number | null
  duration: number | null
  mime_type: string
}

export interface ContentOut {
  id: number
  type: ContentType
  title: string
  slug: string
  summary: string | null
  body: Record<string, unknown>
  published_at: string | null
  media: MediaOut[]
  source_url?: string | null
  source_provider?: 'soundcloud' | 'youtube' | 'vimeo' | null
  player_url?: string | null
  cover_url?: string | null
  album?: AlbumRef | null
  track_no?: number | null
}

export type AlbumKind = 'album' | 'mixtape' | 'ep' | 'collection'

export interface AlbumRef {
  slug: string
  title: string
  kind: AlbumKind
  year: number | null
}

export interface AlbumOut extends AlbumRef {
  cover_url: string | null
  description: string | null
  track_count: number
}

export interface AlbumDetail extends AlbumOut {
  tracks: ContentOut[]
}

export interface GenreCount {
  name: string
  count: number
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
