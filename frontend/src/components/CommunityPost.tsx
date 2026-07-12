import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import type { ContentOut } from '../api/types'
import {
  community,
  communityWsUrl,
  type CommentOut,
  type CommunityEvent,
  type InteractionOut,
  type ReactionKind,
} from '../api/community'
import {
  BookmarkIcon,
  CommentIcon,
  ReactionIcon,
  REACTION_COLOR,
  REACTION_LABEL,
  REACTION_ORDER,
  ThumbIcon,
} from './reactionIcons'
import './CommunityPost.css'

function fmtDate(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
}
function fmtTime(iso: string) {
  const d = new Date(iso)
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')} ${fmtDate(iso)}`
}

/** Thẻ bài cộng đồng kiểu Facebook (giữ style Eskaylation):
    header + caption + ảnh, thanh cảm xúc (6 loại, hover chọn), lưu bài,
    và khu bình luận realtime (WebSocket) mở khi bấm "Bình luận". */
export function CommunityPost({
  content,
  loggedIn,
}: {
  content: ContentOut
  loggedIn: boolean
}) {
  const id = content.id
  const author =
    typeof content.body.author === 'string' ? content.body.author : content.title

  const [inter, setInter] = useState<InteractionOut | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [comments, setComments] = useState<CommentOut[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    let alive = true
    community
      .interactions(id)
      .then((d) => alive && setInter(d))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [id])

  // Tải bình luận + mở WebSocket khi khu bình luận được mở
  useEffect(() => {
    if (!expanded) return
    let alive = true
    community
      .comments(id)
      .then((page) => alive && setComments(page.items))
      .catch(() => {})

    const ws = new WebSocket(communityWsUrl(id))
    ws.onmessage = (e) => {
      if (!alive) return
      let ev: CommunityEvent
      try {
        ev = JSON.parse(e.data)
      } catch {
        return
      }
      if (ev.kind === 'comment') appendComment(ev.comment)
      else if (ev.kind === 'reaction')
        setInter((cur) =>
          cur
            ? { ...cur, reactions: { ...cur.reactions, counts: ev.counts, total: ev.total } }
            : cur,
        )
    }
    return () => {
      alive = false
      ws.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, id])

  function appendComment(c: CommentOut) {
    setComments((cur) => (cur.some((x) => x.id === c.id) ? cur : [...cur, c]))
    setInter((cur) =>
      cur ? { ...cur, comment_count: cur.comment_count + 1 } : cur,
    )
  }

  async function pickReaction(kind: ReactionKind) {
    setPickerOpen(false)
    try {
      const summary = await community.react(id, kind)
      setInter((cur) => (cur ? { ...cur, reactions: summary } : cur))
    } catch {
      /* bỏ qua */
    }
  }

  async function toggleLike() {
    if (!inter) return
    try {
      const summary = inter.reactions.my_reaction
        ? await community.unreact(id)
        : await community.react(id, 'like')
      setInter((cur) => (cur ? { ...cur, reactions: summary } : cur))
    } catch {
      /* bỏ qua */
    }
  }

  async function toggleSave() {
    if (!inter) return
    try {
      const res = inter.saved ? await community.unsave(id) : await community.save(id)
      setInter((cur) => (cur ? { ...cur, saved: res.saved } : cur))
    } catch {
      /* bỏ qua */
    }
  }

  async function submitComment(e: FormEvent) {
    e.preventDefault()
    const body = draft.trim()
    if (!body || sending) return
    setSending(true)
    try {
      const c = await community.addComment(id, body)
      appendComment(c)
      setDraft('')
    } catch {
      /* bỏ qua */
    } finally {
      setSending(false)
    }
  }

  const counts = inter?.reactions.counts ?? {}
  const total = inter?.reactions.total ?? 0
  const mine = inter?.reactions.my_reaction ?? null
  const topKinds = REACTION_ORDER.filter((k) => counts[k] > 0)
    .sort((a, b) => counts[b] - counts[a])
    .slice(0, 3)
  const media = content.media

  return (
    <article className="cpost">
      <header className="cpost__head">
        <span className="cpost__avatar" aria-hidden="true" />
        <div className="cpost__id">
          <span className="cpost__name">{author}</span>
          <div className="cpost__meta">
            <time>{fmtDate(content.published_at)}</time>
            <span className="cpost__dot" aria-hidden="true" />
            <span>Cộng đồng</span>
          </div>
        </div>
      </header>

      {content.summary && <p className="cpost__caption">{content.summary}</p>}

      {media.length > 0 && (
        <div
          className={`cpost__media cpost__media--n${Math.min(media.length, 4)}`}
        >
          {media.slice(0, 4).map((m, i) => (
            <div className="cpost__cell" key={i}>
              <img src={m.url} alt={m.alt_text ?? ''} loading="lazy" />
              {i === 3 && media.length > 4 && (
                <span className="cpost__more">+{media.length - 4}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tổng quan reactions + số bình luận */}
      {(total > 0 || (inter?.comment_count ?? 0) > 0) && (
        <div className="cpost__stats">
          <span className="cpost__stats-emojis">
            {topKinds.map((k) => (
              <span
                key={k}
                className="cpost__stats-icon"
                style={{ color: REACTION_COLOR[k] }}
              >
                <ReactionIcon kind={k} />
              </span>
            ))}
            {total > 0 && <span className="cpost__stats-count">{total}</span>}
          </span>
          {(inter?.comment_count ?? 0) > 0 && (
            <button
              type="button"
              className="cpost__stats-comments"
              onClick={() => setExpanded(true)}
            >
              {inter?.comment_count} bình luận
            </button>
          )}
        </div>
      )}

      {/* Thanh hành động */}
      <div className="cpost__actions">
        <div
          className="cpost__react-wrap"
          onMouseEnter={() => loggedIn && setPickerOpen(true)}
          onMouseLeave={() => setPickerOpen(false)}
        >
          <button
            type="button"
            className={mine ? 'cpost__act cpost__act--on' : 'cpost__act'}
            onClick={toggleLike}
            disabled={!loggedIn}
            style={mine ? { color: REACTION_COLOR[mine] } : undefined}
          >
            <span className="cpost__act-icon">
              {mine ? <ReactionIcon kind={mine} /> : <ThumbIcon />}
            </span>
            {mine ? REACTION_LABEL[mine] : 'Thích'}
          </button>
          {pickerOpen && (
            <div className="cpost__picker">
              {REACTION_ORDER.map((k) => (
                <button
                  key={k}
                  type="button"
                  className="cpost__picker-item"
                  title={REACTION_LABEL[k]}
                  style={{ color: REACTION_COLOR[k] }}
                  onClick={() => pickReaction(k)}
                >
                  <ReactionIcon kind={k} />
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          className="cpost__act"
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="cpost__act-icon">
            <CommentIcon />
          </span>
          Bình luận
        </button>

        <button
          type="button"
          className={inter?.saved ? 'cpost__act cpost__act--on' : 'cpost__act'}
          onClick={toggleSave}
          disabled={!loggedIn}
        >
          <span className="cpost__act-icon">
            <BookmarkIcon filled={inter?.saved} />
          </span>
          {inter?.saved ? 'Đã lưu' : 'Lưu'}
        </button>
      </div>

      {/* Khu bình luận */}
      {expanded && (
        <div className="cpost__comments">
          {comments.length === 0 && (
            <p className="cpost__comments-empty">Chưa có bình luận. Hãy là người đầu tiên!</p>
          )}
          {comments.map((c) => (
            <div className="cpost__comment" key={c.id}>
              <span className="cpost__comment-avatar" aria-hidden="true" />
              <div className="cpost__comment-bubble">
                <span className="cpost__comment-author">{c.author_name}</span>
                <span className="cpost__comment-body">{c.body}</span>
                <time className="cpost__comment-time">{fmtTime(c.created_at)}</time>
              </div>
            </div>
          ))}

          {loggedIn ? (
            <form className="cpost__form" onSubmit={submitComment}>
              <input
                className="cpost__input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Viết bình luận..."
                maxLength={2000}
              />
              <button
                type="submit"
                className="cpost__send"
                disabled={sending || !draft.trim()}
              >
                Gửi
              </button>
            </form>
          ) : (
            <p className="cpost__login-hint">
              <Link to="/login">Đăng nhập</Link> để bình luận và bày tỏ cảm xúc.
            </p>
          )}
        </div>
      )}
    </article>
  )
}
