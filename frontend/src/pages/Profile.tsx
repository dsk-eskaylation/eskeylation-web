import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { getSession, updateProfile, type SessionUser } from '../api/auth'
import { community } from '../api/community'
import type { ContentOut } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { MediaImage } from '../components/MediaImage'
import { artistOf, audioUrl, coverUrl, usePlayer } from '../player/PlayerContext'
import './Profile.css'

type Tab = 'posts' | 'favorites' | 'saved'
type Load<T> = { status: 'loading' } | { status: 'error' } | { status: 'ready'; items: T[] }

function useList(fetcher: () => Promise<ContentOut[]>): Load<ContentOut> {
  const [state, setState] = useState<Load<ContentOut>>({ status: 'loading' })
  const fetchRef = useRef(fetcher)
  useEffect(() => {
    let live = true
    fetchRef.current().then((items) => live && setState({ status: 'ready', items }), () => live && setState({ status: 'error' }))
    return () => { live = false }
  }, [])
  return state
}

const count = (state: Load<ContentOut>) => (state.status === 'ready' ? state.items.length : '–')

/** Hồ sơ cá nhân kiểu mạng xã hội: bài đăng, bài hát yêu thích, bài đã lưu (riêng tư). */
export function Profile() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined)

  useEffect(() => {
    let live = true
    getSession().then((u) => live && setUser(u))
    return () => { live = false }
  }, [])

  if (user === undefined) return null
  if (user === null) return <Navigate to="/login?next=%2Fprofile" replace />
  return <ProfileView user={user} />
}

/** Chỉ render khi đã đăng nhập, nên các danh sách riêng tư không bị gọi lúc chưa có phiên. */
function ProfileView({ user }: { user: SessionUser }) {
  const [tab, setTab] = useState<Tab>('posts')
  const posts = useList(() => community.myPosts())
  const favorites = useList(() => community.mySaved('music').then((p) => p.items))
  const saved = useList(() => community.mySaved('community').then((p) => p.items))
  const name = user.email.split('@', 1)[0]
  const joined = user.created_at ? new Date(user.created_at).toLocaleDateString('vi-VN', { month: 'long', year: 'numeric' }) : null

  const tabs: { key: Tab; label: string; icon: ReactNode; total: number | string }[] = [
    { key: 'posts', label: 'Bài đăng', total: count(posts), icon: <path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /> },
    { key: 'favorites', label: 'Yêu thích', total: count(favorites), icon: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" /> },
    { key: 'saved', label: 'Đã lưu', total: count(saved), icon: <path d="M6 3h12v18l-6-4-6 4z" /> },
  ]

  return (
    <div className="profile">
      <header className="profile__head">
        <span className="profile__avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
        <div className="profile__info">
          <div className="profile__name-row">
            <h1>{name}</h1>
          </div>
          <ul className="profile__stats">
            {tabs.map((t) => (
              <li key={t.key}><strong>{t.total}</strong> {t.label.toLowerCase()}</li>
            ))}
          </ul>
          <BioEditor initial={user.bio ?? ''} />
          {joined && <p className="profile__joined">Tham gia {joined}</p>}
        </div>
      </header>

      <div className="profile__tabs" role="tablist" aria-label="Nội dung hồ sơ">
        {tabs.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}>
            <svg viewBox="0 0 24 24" aria-hidden="true">{t.icon}</svg>
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {tab === 'posts' && <PostGrid state={posts} empty="Bạn chưa đăng bài nào. Vào Cộng đồng và bấm “+ Đăng bài”." />}
        {tab === 'favorites' && <Favorites state={favorites} />}
        {tab === 'saved' && <PostGrid state={saved} empty="Bấm Lưu trên bài cộng đồng để xem lại ở đây." />}
      </div>
    </div>
  )
}

function BioEditor({ initial }: { initial: string }) {
  const [bio, setBio] = useState(initial)
  const [draft, setDraft] = useState(initial)
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      const user = await updateProfile(draft)
      setBio(user.bio ?? '')
      setEditing(false)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Chưa lưu được bio.')
    } finally {
      setBusy(false)
    }
  }

  if (!editing) {
    return (
      <div className="profile__bio">
        {bio ? <p>{bio}</p> : <p className="profile__muted">Chưa có bio.</p>}
        <button type="button" className="profile__edit" onClick={() => { setDraft(bio); setEditing(true) }}>Sửa hồ sơ</button>
      </div>
    )
  }
  return (
    <div className="profile__bio profile__bio--editing">
      <label htmlFor="profile-bio" className="profile__muted">Bio</label>
      <textarea id="profile-bio" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={500} rows={3} placeholder="Giới thiệu đôi chút về bạn" autoFocus />
      <div className="profile__actions">
        <button type="button" className="profile__edit profile__edit--primary" onClick={save} disabled={busy}>Lưu</button>
        <button type="button" className="profile__edit" onClick={() => setEditing(false)} disabled={busy}>Huỷ</button>
        <span className="profile__muted">{draft.length}/500</span>
      </div>
      {msg && <p role="alert">{msg}</p>}
    </div>
  )
}

function PostGrid({ state, empty }: { state: Load<ContentOut>; empty: string }) {
  const navigate = useNavigate()
  if (state.status === 'loading') return <p role="status" className="profile__muted">Đang tải…</p>
  if (state.status === 'error') return <EmptyState title="Không tải được danh sách." />
  if (state.items.length === 0) return <EmptyState title={empty} />
  return (
    <ul className="profile__grid">
      {state.items.map((post) => {
        const pending = post.body.review_status === 'draft'
        const image = post.media.find((m) => m.mime_type.startsWith('image/') && m.url)
        return (
          <li key={post.id}>
            <button
              type="button"
              className="profile__tile"
              disabled={pending}
              onClick={() => navigate(`/community?post=${encodeURIComponent(post.slug)}`)}
              aria-label={pending ? `${post.title} (chờ duyệt)` : `Mở bài ${post.title}`}
            >
              {image ? (
                <MediaImage media={image} alt="" sizes="(max-width: 640px) 33vw, 300px" />
              ) : (
                <span className="profile__tile-text">{post.title}</span>
              )}
              {pending && <span className="profile__badge">Chờ duyệt</span>}
              {post.media.length > 1 && <span className="profile__multi" aria-hidden="true">❐</span>}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function Favorites({ state }: { state: Load<ContentOut> }) {
  const player = usePlayer()
  if (state.status === 'loading') return <p role="status" className="profile__muted">Đang tải…</p>
  if (state.status === 'error') return <EmptyState title="Không tải được bài hát yêu thích." />
  if (state.items.length === 0) return <EmptyState title="Bấm ♡ trên trình phát để thêm bài hát vào đây." />
  const playable = state.items.filter((track) => audioUrl(track))
  return (
    <>
      {playable.length > 0 && (
        <button type="button" className="profile__edit profile__edit--primary profile__play" onClick={() => player.playQueue(playable, 0)}>
          Phát {playable.length} bài yêu thích
        </button>
      )}
      <ol className="profile__songs">
        {state.items.map((track) => {
          const cover = coverUrl(track)
          return (
            <li key={track.id}>
              <button
                type="button"
                onClick={() => (audioUrl(track) ? player.playQueue(playable, playable.indexOf(track)) : player.playEmbed(track))}
              >
                {cover ? <img src={cover} alt="" loading="lazy" /> : <span className="profile__cover" aria-hidden="true" />}
                <span className="profile__song">
                  <span>{track.title}</span>
                  <span className="profile__muted">{artistOf(track)}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </>
  )
}
