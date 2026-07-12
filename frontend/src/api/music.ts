import { csrfHeaders } from './auth'

export interface LyricAck {
  ok: boolean
  message: string
}

/** Gửi đóng góp lời bài hát (cần đăng nhập). Ném lỗi nếu 401/khác. */
export async function submitLyrics(
  contentId: number,
  body: string,
): Promise<LyricAck> {
  const res = await fetch(`/api/music/${contentId}/lyrics`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ body }),
  })
  if (res.status === 401) throw new Error('Bạn cần đăng nhập để đóng góp lời.')
  if (!res.ok) throw new Error('Gửi đóng góp thất bại. Thử lại sau.')
  return res.json() as Promise<LyricAck>
}
