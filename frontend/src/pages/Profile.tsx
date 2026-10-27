import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { getSession, updateProfile, type SessionUser } from '../api/auth'
import { community } from '../api/community'
import type { ContentOut } from '../api/types'
import { CommunityPost } from '../components/CommunityPost'
import { EmptyState } from '../components/EmptyState'
import { artistOf, audioUrl, usePlayer } from '../player/PlayerContext'
import './Profile.css'

type Tab = 'music' | 'community'

/** Hồ sơ cá nhân: bio + bài hát yêu thích + bài cộng đồng đã lưu (đều riêng tư). */
export function Profile() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined)
  const [tab, setTab] = useState<Tab>('music')

  useEffect(() => {
    let live = true
    getSession().then((u) => live && setUser(u))
    return () => { live = false }
  }, [])

  if (user === undefined) return null
  if (user === null) return <Navigate to="/login?next=%2Fprofile" replace />

  return (
    <div className="profile">
      <header className="profile__head">
        <h1>{user.email.split('@', 1)[0]}</h1>
        <BioEditor initial={user.bio ?? ''} />
      </header>
      <div className="profile__tabs" role="tablist" aria-label="Danh sách của tôi">
        <button type="button" role="tab" aria-selected={tab === 'music'} onClick={() => setTab('music')}>
          Bài hát yêu thích
        </button>
        <button type="button" role="tab" aria-selected={tab === 'community'} onClick={() => setTab('community')}>
          Bài đã lưu
        </button>
      </div>
      <div role="tabpanel">
        {tab === 'music' ? <Favorites /> : <SavedPosts />}
      </div>
    </div>
  )
}

function BioEditor({ initial }: { initial: string }) {
  const [bio, setBio] = useState(initial)
  const [saved, setSaved] = useState(initial)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      const user = await updateProfile(bio)
      setBio(user.bio ?? '')
      setSaved(user.bio ?? '')
      setMsg('Đã lưu bio.')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Chưa lưu được bio.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="profile__bio">
      <label htmlFor="profile-bio">Bio</label>
      <textarea id="profile-bio" value={bio} onChange={(e) => setBio(e.target.value)} maxLength={500} rows={3} placeholder="Giới thiệu đôi chút về bạn…" />
      <button type="button" onClick={save} disabled={busy || bio === saved}>Lưu bio</button>
      {msg && <p role="status">{msg}</p>}
    </div>
  )
}

function useSaved(type: Tab) {
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error' } | { status: 'ready'; items: ContentOut[] }>({ status: 'loading' })
  useEffect(() => {
    let live = true
    community.mySaved(type).then(
      (page) => live && setState({ status: 'ready', items: page.items }),
      () => live && setState({ status: 'error' }),
    )
    return () => { live = false }
  }, [type])
  return state
}

function Favorites() {
  const state = useSaved('music')
  const player = usePlayer()
  if (state.status === 'loading') return <p role="status">Đang tải…</p>
  if (state.status === 'error') return <EmptyState title="Không tải được bài hát yêu thích." />
  if (state.items.length === 0) return <EmptyState title="Chưa có bài hát yêu thích." hint="Bấm ♡ trên trình phát để thêm bài." />
  const playable = state.items.filter((track) => audioUrl(track))

  return (
    <>
      {playable.length > 0 && (
        <button type="button" className="profile__play" onClick={() => player.playQueue(playable, 0)}>
          Phát {playable.length} bài yêu thích
        </button>
      )}
      <ol className="profile__songs">
        {state.items.map((track) => (
          <li key={track.id}>
            <button
              type="button"
              onClick={() => audioUrl(track) ? player.playQueue(playable, playable.indexOf(track)) : player.playEmbed(track)}
            >
              <span>{track.title}</span>
              <span className="profile__artist">{artistOf(track)}</span>
            </button>
          </li>
        ))}
      </ol>
    </>
  )
}

function SavedPosts() {
  const state = useSaved('community')
  if (state.status === 'loading') return <p role="status">Đang tải…</p>
  if (state.status === 'error') return <EmptyState title="Không tải được bài đã lưu." />
  if (state.items.length === 0) return <EmptyState title="Chưa lưu bài nào." />
  return (
    <div className="profile__posts">
      {state.items.map((post) => <CommunityPost key={post.id} content={post} loggedIn />)}
    </div>
  )
}
