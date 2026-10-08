export type ContentType = 'music' | 'gallery' | 'community' | 'homepage'

export interface MediaOut {
  url: string
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
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
