import type { ContentOut, Page } from './types'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new ApiError(res.status, `Request lỗi ${res.status}: ${path}`)
  }
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export interface ListParams {
  page?: number
  pageSize?: number
  q?: string
  category?: string
  artist?: string
}

function buildQuery(params: ListParams): string {
  const sp = new URLSearchParams()
  if (params.page) sp.set('page', String(params.page))
  if (params.pageSize) sp.set('page_size', String(params.pageSize))
  if (params.q) sp.set('q', params.q)
  if (params.category) sp.set('category', params.category)
  if (params.artist) sp.set('artist', params.artist)
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

export const api = {
  homepage: () => getJson<ContentOut>('/api/homepage'),
  list: (type: 'music' | 'photos' | 'community', params: ListParams = {}) =>
    getJson<Page<ContentOut>>(`/api/${type}${buildQuery(params)}`),
  detail: (type: 'music' | 'photos' | 'community', slug: string) =>
    getJson<ContentOut>(`/api/${type}/${slug}`),
}
