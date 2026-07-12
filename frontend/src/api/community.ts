import { csrfHeaders } from './auth'
import type { Page } from './types'

export type ReactionKind = 'like' | 'love' | 'haha' | 'wow' | 'sad' | 'angry'

export interface CommentOut {
  id: number
  content_id: number
  body: string
  author_name: string
  created_at: string
}

export interface ReactionSummary {
  counts: Record<string, number>
  total: number
  my_reaction: ReactionKind | null
}

export interface InteractionOut {
  content_id: number
  reactions: ReactionSummary
  comment_count: number
  saved: boolean
}

/** Sự kiện realtime nhận qua WebSocket. */
export type CommunityEvent =
  | { kind: 'comment'; comment: CommentOut }
  | { kind: 'reaction'; counts: Record<string, number>; total: number }

async function toJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Yêu cầu lỗi ${res.status}`)
  return res.json() as Promise<T>
}

const base = (id: number) => `/api/community/${id}`
const jsonMut = () => ({ 'Content-Type': 'application/json', ...csrfHeaders() })

export const community = {
  interactions: (id: number) =>
    fetch(`${base(id)}/interactions`, { credentials: 'include' }).then((r) =>
      toJson<InteractionOut>(r),
    ),
  comments: (id: number, page = 1) =>
    fetch(`${base(id)}/comments?page=${page}&page_size=50`, {
      credentials: 'include',
    }).then((r) => toJson<Page<CommentOut>>(r)),
  addComment: (id: number, body: string) =>
    fetch(`${base(id)}/comments`, {
      method: 'POST',
      credentials: 'include',
      headers: jsonMut(),
      body: JSON.stringify({ body }),
    }).then((r) => toJson<CommentOut>(r)),
  react: (id: number, type: ReactionKind) =>
    fetch(`${base(id)}/reaction`, {
      method: 'PUT',
      credentials: 'include',
      headers: jsonMut(),
      body: JSON.stringify({ type }),
    }).then((r) => toJson<ReactionSummary>(r)),
  unreact: (id: number) =>
    fetch(`${base(id)}/reaction`, {
      method: 'DELETE',
      credentials: 'include',
      headers: csrfHeaders(),
    }).then((r) => toJson<ReactionSummary>(r)),
  save: (id: number) =>
    fetch(`${base(id)}/save`, {
      method: 'PUT',
      credentials: 'include',
      headers: csrfHeaders(),
    }).then((r) => toJson<{ saved: boolean }>(r)),
  unsave: (id: number) =>
    fetch(`${base(id)}/save`, {
      method: 'DELETE',
      credentials: 'include',
      headers: csrfHeaders(),
    }).then((r) => toJson<{ saved: boolean }>(r)),
}

/** URL WebSocket realtime cho một bài (đi qua proxy /api ở dev). */
export function communityWsUrl(id: number): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/community/${id}/ws`
}
