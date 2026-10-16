import type { ContentOut, Page } from './types'

const publicCache = new Map<string, { expires: number; value: Promise<unknown> }>()

export function invalidatePublicCache() {
  publicCache.clear()
}

async function getJson<T>(path: string): Promise<T> {
  const cached = publicCache.get(path)
  if (cached && cached.expires > Date.now()) return cached.value as Promise<T>
  const value = (async () => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 20000)
    try {
      const res = await fetch(path, { credentials: 'omit', signal: controller.signal })
      if (!res.ok) throw new ApiError(res.status, `Request lỗi ${res.status}: ${path}`)
      return await res.json() as T
    } catch (error) {
      publicCache.delete(path)
      throw error
    } finally {
      clearTimeout(timer)
    }
  })()
  if (publicCache.size >= 64) publicCache.delete(publicCache.keys().next().value!)
  publicCache.set(path, { expires: Date.now() + 15000, value })
  return value
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

async function listAll(type: 'photos' | 'video' | 'music'): Promise<Page<ContentOut>> {
  const first = await api.list(type, { pageSize: 60 })
  const rest: Page<ContentOut>[] = []
  for (let page = 2; page <= first.pages; page += 3) {
    rest.push(...await Promise.all(
      Array.from({ length: Math.min(3, first.pages - page + 1) }, (_, i) => api.list(type, { pageSize: 60, page: page + i })),
    ))
  }
  return { ...first, items: first.items.concat(...rest.map((p) => p.items)) }
}

export const api = {
  listAll,
  homepage: () => getJson<ContentOut>('/api/homepage'),
  list: (type: 'music' | 'photos' | 'community' | 'video', params: ListParams = {}) =>
    getJson<Page<ContentOut>>(`/api/${type}${buildQuery(params)}`),
  detail: (type: 'music' | 'photos' | 'community' | 'video', slug: string) =>
    getJson<ContentOut>(`/api/${type}/${slug}`),
}
