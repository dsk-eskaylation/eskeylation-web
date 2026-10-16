import { csrfHeaders } from './auth'
import type { Page } from './types'

export type ReactionKind = 'like' | 'love' | 'haha' | 'wow' | 'sad' | 'angry'

export interface ReactionSummary {
  counts: Record<string, number>
  total: number
  my_reaction: ReactionKind | null
}

export interface CommentOut {
  id: number
  content_id: number
  body: string
  author_name: string
  created_at: string
  updated_at: string
  edited: boolean
  reactions: ReactionSummary
  is_mine: boolean
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
  | { kind: 'comment_edit'; comment: CommentOut }
  | { kind: 'comment_delete'; comment_id: number }
  | { kind: 'reaction'; counts: Record<string, number>; total: number }

/** Đọc JSON, hoặc ném Error KÈM 'detail' từ server (vd cảnh báo từ cấm). */
async function toJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw await toError(res)
  return res.json() as Promise<T>
}

async function ensureOk(res: Response): Promise<void> {
  if (!res.ok) throw await toError(res)
}

async function toError(res: Response): Promise<Error> {
  const data = await res.json().catch(() => null)
  const detail =
    data && typeof data.detail === 'string' ? data.detail : `Yêu cầu lỗi ${res.status}`
  return new Error(detail)
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
  editComment: (id: number, commentId: number, body: string) =>
    fetch(`${base(id)}/comments/${commentId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: jsonMut(),
      body: JSON.stringify({ body }),
    }).then((r) => toJson<CommentOut>(r)),
  deleteComment: (id: number, commentId: number) =>
    fetch(`${base(id)}/comments/${commentId}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: csrfHeaders(),
    }).then(ensureOk),
  reactComment: (id: number, commentId: number, type: ReactionKind) =>
    fetch(`${base(id)}/comments/${commentId}/reaction`, {
      method: 'PUT',
      credentials: 'include',
      headers: jsonMut(),
      body: JSON.stringify({ type }),
    }).then((r) => toJson<ReactionSummary>(r)),
  unreactComment: (id: number, commentId: number) =>
    fetch(`${base(id)}/comments/${commentId}/reaction`, {
      method: 'DELETE',
      credentials: 'include',
      headers: csrfHeaders(),
    }).then((r) => toJson<ReactionSummary>(r)),
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
