/** Client API khu vực quản trị (/admin/*). Mọi request kèm Bearer token;
    gặp 401 thì xoá token để RequireAuth đá về /login. */

import { authHeaders, clearToken } from './auth'
import type { Page } from './types'

export type ContentType = 'music' | 'gallery' | 'community' | 'homepage'
export type ContentStatus = 'draft' | 'published' | 'archived'
export type UserRole = 'admin' | 'editor' | 'author'

export interface AdminUser {
  id: number
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface AdminMediaItem {
  media_id: number
  url: string
  caption: string | null
  position: number
  is_primary: boolean
  mime_type: string
  width: number | null
  height: number | null
  duration: number | null
  alt_text: string | null
}

export interface ContentAdmin {
  id: number
  type: ContentType
  title: string
  slug: string
  status: ContentStatus
  summary: string | null
  body: Record<string, unknown>
  author_id: number | null
  published_at: string | null
  created_at: string
  updated_at: string
  media: AdminMediaItem[]
}

export interface MediaUploaded {
  id: number
  url: string
  mime_type: string
}

export interface ContentMediaIn {
  media_id: number
  caption?: string | null
  position?: number
  is_primary?: boolean
}

export interface ContentPayload {
  title?: string
  summary?: string | null
  body?: Record<string, unknown>
  media?: ContentMediaIn[]
}

export class AdminApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers ?? {}) },
  })
  if (res.status === 401) {
    clearToken()
    throw new AdminApiError(401, 'Phiên đăng nhập hết hạn')
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail =
      typeof data?.detail === 'string' ? data.detail : `Lỗi ${res.status}`
    throw new AdminApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function jsonInit(method: string, payload: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }
}

export const adminApi = {
  list: (params: { type?: ContentType; status?: ContentStatus; page?: number }) => {
    const sp = new URLSearchParams()
    if (params.type) sp.set('type', params.type)
    if (params.status) sp.set('content_status', params.status)
    sp.set('page', String(params.page ?? 1))
    sp.set('page_size', '50')
    return request<Page<ContentAdmin>>(`/admin/content?${sp}`)
  },

  create: (payload: ContentPayload & { type: ContentType; title: string }) =>
    request<ContentAdmin>('/admin/content', jsonInit('POST', payload)),

  update: (id: number, payload: ContentPayload) =>
    request<ContentAdmin>(`/admin/content/${id}`, jsonInit('PATCH', payload)),

  remove: (id: number) =>
    request<void>(`/admin/content/${id}`, { method: 'DELETE' }),

  publish: (id: number) =>
    request<ContentAdmin>(`/admin/content/${id}/publish`, { method: 'POST' }),

  unpublish: (id: number) =>
    request<ContentAdmin>(`/admin/content/${id}/unpublish`, { method: 'POST' }),

  archive: (id: number) =>
    request<ContentAdmin>(`/admin/content/${id}/archive`, { method: 'POST' }),

  duplicate: (id: number) =>
    request<ContentAdmin>(`/admin/content/${id}/duplicate`, { method: 'POST' }),

  uploadMedia: (file: File, altText?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (altText) form.append('alt_text', altText)
    return request<MediaUploaded>('/admin/media', { method: 'POST', body: form })
  },

  // Tài khoản đang đăng nhập (để biết vai trò)
  me: () => request<AdminUser>('/auth/me'),

  // ---- Quản lý tài khoản (chỉ admin; editor/author gọi sẽ nhận 403) ----
  listUsers: () => request<AdminUser[]>('/admin/users'),

  updateUser: (id: number, payload: { is_active?: boolean; role?: UserRole }) =>
    request<AdminUser>(`/admin/users/${id}`, jsonInit('PATCH', payload)),

  createUser: (payload: { email: string; password: string; role?: UserRole }) =>
    request<AdminUser>('/admin/users', jsonInit('POST', payload)),
}
