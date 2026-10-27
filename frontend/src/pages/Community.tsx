import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Pagination } from '../components/Pagination'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import { getSession } from '../api/auth'
import { CommunityPost } from '../components/CommunityPost'
import { EmptyState } from '../components/EmptyState'
import { Modal } from '../components/Modal'
import { PostComposer } from '../components/PostComposer'
import type { ContentOut } from '../api/types'
import './Community.css'

const TABS = [
  { key: 'intro', label: 'Lời mở đầu' },
  { key: 'feed', label: 'Cộng đồng' },
  { key: 'products', label: 'Sản phẩm' },
  { key: 'support', label: 'Ủng hộ' },
] as const
type Tab = (typeof TABS)[number]['key']

const DEFAULT_INTRO =
  'Website phi lợi nhuận được lập ra cho cộng đồng Eskaylation nhằm lưu giữ những tài nguyên quý báu mà DSK đã sáng tạo ra. ' +
  'Âm nhạc vì âm nhạc, âm nhạc tạo ra anh và anh cũng tạo ra âm nhạc, chúng tôi mạn phép được lưu giữ tập trung những tài nguyên của anh ở đây như một phần kỉ niệm.'
const DEFAULT_RULES = 'Yêu cầu tôn trọng, văn minh, hòa đồng.'
const DEFAULT_PRODUCT_INTRO = 'Việc bán các ấn phẩm liên quan đến Eskaylation nhằm duy trì, vận hành website, cộng đồng về lâu dài.'
const DEFAULT_SUPPORT_INTRO = 'Việc kêu gọi ủng hộ nhằm duy trì, vận hành website, cộng đồng về lâu dài.'

/** Trang Cộng đồng — feed dọc kiểu Facebook (giữ style Eskaylation):
    mỗi bài có cảm xúc, bình luận realtime (WebSocket), lưu bài. */
export function Community() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [userName, setUserName] = useState('')
  const [params, setParams] = useSearchParams()
  const tabParam = params.get('tab')
  const tab: Tab = TABS.some((t) => t.key === tabParam) ? tabParam as Tab : 'feed'
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
    getSession().then((u) => {
      if (!alive) return
      setLoggedIn(u !== null)
      setIsAdmin(u?.role === 'admin')
      setUserName(u ? u.email.split('@', 1)[0] : '')
    })
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

  const openSlug = params.get('post')
  function openPost(slug: string | null) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (slug) next.set('post', slug)
      else next.delete('post')
      return next
    })
  }

  function goTab(next: Tab) {
    setParams(next === 'feed' ? {} : { tab: next })
  }

  const nav = (
    <nav className="community__tabs" aria-label="Mục cộng đồng">
      {TABS.map((t) => (
        <button key={t.key} type="button" aria-current={tab === t.key ? 'page' : undefined} onClick={() => goTab(t.key)}>
          {t.label}
        </button>
      ))}
    </nav>
  )

  if (tab !== 'feed') {
    return (
      <div className="community">
        <h1 className="sr-only">Cộng đồng Eskaylation — {TABS.find((t) => t.key === tab)?.label}</h1>
        {nav}
        <CommunityInfo tab={tab} />
      </div>
    )
  }

  return (
    <div className="community">
      <h1 className="sr-only">Cộng đồng Eskaylation</h1>
      {nav}
      {loggedIn && <PostComposer name={userName} />}
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
            isAdmin={isAdmin}
            priority={index === 0}
            onOpen={() => openPost(item.slug)}
          />
        ))}
      </div>
      {openSlug && (
        <PostDetail
          slug={openSlug}
          cached={items.find((item) => item.slug === openSlug)}
          loggedIn={loggedIn}
          isAdmin={isAdmin}
          onClose={() => openPost(null)}
        />
      )}
      {state.status === 'success' && (
        <Pagination page={Math.min(page, Math.max(1, state.data.pages))}
          pages={state.data.pages} label="Phân trang cộng đồng" onChange={goPage} busy={busy} />
      )}
    </div>
  )
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
const str = (value: unknown) => (typeof value === 'string' ? value.trim() : '')

/** Lời mở đầu / Sản phẩm / Ủng hộ — admin sửa trong CMS (Trang chủ → Trang Cộng đồng). */
function CommunityInfo({ tab }: { tab: Exclude<Tab, 'feed'> }) {
  const state = useLiveApi(() => api.homepage())
  if (state.status === 'loading') return <div className="community__info" aria-busy="true" />
  if (state.status === 'error') return <EmptyState title="Không tải được nội dung." />
  const body = record(state.data.body)
  const imageUrl = (id: unknown) => state.data.media.find((m) => m.media_id === id)?.url

  if (tab === 'intro') {
    return (
      <section className="community__info">
        <h2>Lời mở đầu</h2>
        <p>{str(body.community_intro) || DEFAULT_INTRO}</p>
        <h3>Văn hóa cộng đồng</h3>
        <p>{str(body.community_rules) || DEFAULT_RULES}</p>
      </section>
    )
  }

  if (tab === 'products') {
    const product = record(body.product)
    const image = imageUrl(product.media_id)
    const formUrl = str(product.form_url)
    return (
      <section className="community__info">
        <h2>Sản phẩm</h2>
        <p className="community__muted">{DEFAULT_PRODUCT_INTRO}</p>
        {str(product.name) ? (
          <article className="community__card">
            {image && <img src={image} alt={str(product.name)} />}
            <h3>{str(product.name)}</h3>
            {str(product.description) && <p>{str(product.description)}</p>}
            {formUrl && <a className="page-action" href={formUrl} target="_blank" rel="noopener noreferrer">Đăng ký mua</a>}
          </article>
        ) : (
          <EmptyState title="Hiện không có sản phẩm nào." />
        )}
      </section>
    )
  }

  const support = record(body.support)
  const qr = imageUrl(support.qr_media_id)
  const statements = Array.isArray(support.statements)
    ? support.statements.filter((url): url is string => typeof url === 'string')
    : []
  return (
    <section className="community__info">
      <h2>Ủng hộ</h2>
      <p className="community__muted">{str(support.intro) || DEFAULT_SUPPORT_INTRO}</p>
      {str(support.amount) && <p className="community__amount">Số tiền hiện tại: <strong>{str(support.amount)} VNĐ</strong></p>}
      {str(support.used) && <p>{str(support.used)}</p>}
      {qr && <img className="community__qr" src={qr} alt="Mã QR ủng hộ" />}
      {statements.length > 0 && (
        <>
          <h3>Sao kê</h3>
          <div className="community__statements">
            {statements.map((url, index) => (
              <iframe
                key={url}
                title={`Bài sao kê ${index + 1}`}
                src={`https://www.facebook.com/plugins/post.php?href=${encodeURIComponent(url)}&show_text=true&width=500`}
                loading="lazy"
                sandbox="allow-scripts allow-same-origin allow-popups"
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

/** Bài mở ở dạng Instagram (?post=<slug>); link từ thông báo cũng mở thẳng vào đây. */
function PostDetail({ slug, cached, loggedIn, isAdmin, onClose }: {
  slug: string
  cached: ContentOut | undefined
  loggedIn: boolean
  isAdmin: boolean
  onClose: () => void
}) {
  const [fetched, setFetched] = useState<ContentOut | null | 'error'>(null)
  const [wasListed, setWasListed] = useState(Boolean(cached))
  if (cached && !wasListed) setWasListed(true)
  // Bài đang mở bị gỡ (danh sách làm mới không còn nó) -> đóng khung luôn.
  useEffect(() => {
    if (wasListed && !cached) onClose()
  }, [wasListed, cached, onClose])
  useEffect(() => {
    if (cached || wasListed) return
    let live = true
    api.detail('community', slug).then((post) => live && setFetched(post), () => live && setFetched('error'))
    return () => { live = false }
  }, [slug, cached, wasListed])
  const post = cached ?? (fetched !== 'error' ? fetched : null)
  return (
    <Modal onClose={onClose} variant="bare" label={post ? post.title : 'Bài viết'} showClose>
      {post ? (
        <CommunityPost key={post.id} content={post} loggedIn={loggedIn} isAdmin={isAdmin} variant="detail" />
      ) : fetched === 'error' ? (
        <EmptyState title="Không tìm thấy bài viết này." />
      ) : (
        <p role="status">Đang tải bài viết…</p>
      )}
    </Modal>
  )
}
