import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { getSession } from '../api/auth'
import { CommunityPost } from '../components/CommunityPost'
import { EmptyState } from '../components/EmptyState'
import './Community.css'

/** Trang Cộng đồng — feed dọc kiểu Facebook (giữ style Eskaylation):
    mỗi bài có cảm xúc, bình luận realtime (WebSocket), lưu bài. */
export function Community() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [page, setPage] = useState(1)
  const state = useApi(() => api.list('community', { pageSize: 30, page }), [page])
  const items = state.status === 'success' ? state.data.items : []

  useEffect(() => {
    let alive = true
    getSession().then((u) => alive && setLoggedIn(u !== null))
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="community">
      {state.status === 'loading' && <div className="community__feed" aria-busy="true" />}
      {state.status === 'error' && <EmptyState title="Không tải được bài viết." />}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Hiện tại chưa có bài viết nào TT.  " />
      )}

      <div className="community__feed">
        {items.map((item, index) => (
          <CommunityPost key={item.id} content={item} loggedIn={loggedIn} priority={index === 0} />
        ))}
      </div>
      {state.status === 'success' && state.data.pages > 1 && (
        <nav aria-label="Phân trang cộng đồng">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trang trước</button>
          <span> {page} / {state.data.pages} </span>
          <button type="button" disabled={page >= state.data.pages} onClick={() => setPage(page + 1)}>Trang sau</button>
        </nav>
      )}
    </div>
  )
}
