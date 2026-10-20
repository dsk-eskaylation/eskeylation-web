import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Pagination } from '../components/Pagination'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import { getSession } from '../api/auth'
import { CommunityPost } from '../components/CommunityPost'
import { EmptyState } from '../components/EmptyState'
import './Community.css'

/** Trang Cộng đồng — feed dọc kiểu Facebook (giữ style Eskaylation):
    mỗi bài có cảm xúc, bình luận realtime (WebSocket), lưu bài. */
export function Community() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [params, setParams] = useSearchParams()
  const requestedPage = Number(params.get('page') ?? 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const topRef = useRef<HTMLDivElement>(null)
  const state = useLiveApi(
    () => api.list('community', { pageSize: 30, page }),
    [page],
  )
  const items = state.status === 'success' ? state.data.items : []
  const busy = state.status === 'success' && state.data.page !== page

  useEffect(() => {
    if (state.status === 'success' && page > Math.max(1, state.data.pages)) {
      setParams((previous) => {
        const next = new URLSearchParams(previous)
        if (state.data.pages <= 1) next.delete('page')
        else next.set('page', String(state.data.pages))
        return next
      }, { replace: true })
    }
  }, [state, page, setParams])

  useEffect(() => {
    let alive = true
    getSession().then((u) => alive && setLoggedIn(u !== null))
    return () => {
      alive = false
    }
  }, [])

  function goPage(nextPage: number) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (nextPage === 1) next.delete('page')
      else next.set('page', String(nextPage))
      return next
    })
    topRef.current?.scrollIntoView({ behavior: 'instant', block: 'start' })
  }

  return (
    <div className="community">
      <div ref={topRef} className="community__anchor" aria-hidden="true" />
      {state.status === 'loading' && (
        <div className="community__feed" aria-busy="true" />
      )}
      {state.status === 'error' && (
        <EmptyState title="Không tải được bài viết." />
      )}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Hiện tại chưa có bài viết." />
      )}

      <div className="community__feed" aria-busy={busy}>
        {items.map((item, index) => (
          <CommunityPost
            key={item.id}
            content={item}
            loggedIn={loggedIn}
            priority={index === 0}
          />
        ))}
      </div>
      {state.status === 'success' && (
        <Pagination page={Math.min(page, Math.max(1, state.data.pages))}
          pages={state.data.pages} label="Phân trang cộng đồng" onChange={goPage} busy={busy} />
      )}
    </div>
  )
}
