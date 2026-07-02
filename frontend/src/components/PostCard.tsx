import type { ContentOut } from '../api/types'
import './PostCard.css'

interface Props {
  content: ContentOut
  onClick?: () => void
}

function fmtDate(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')} . ${String(d.getMonth() + 1).padStart(2, '0')}. ${d.getFullYear()}`
}

/** Thẻ bài viết ảnh/cộng đồng (Figma EL-f49357b6):
    header avatar + tên + ngày/vai trò, caption, lưới ảnh 2x2 với ô "+N". */
export function PostCard({ content, onClick }: Props) {
  const shown = content.media.slice(0, 4)
  const extra = content.media.length - 4
  const author =
    typeof content.body.author === 'string' ? content.body.author : content.title

  return (
    <article className="post-card" onClick={onClick}>
      <header className="post-card__head">
        <span className="post-card__avatar" aria-hidden="true" />
        <div className="post-card__id">
          <span className="post-card__name">{author}</span>
          <div className="post-card__meta">
            <time>{fmtDate(content.published_at)}</time>
            <span className="post-card__dot" aria-hidden="true" />
            <span>Admin</span>
          </div>
        </div>
      </header>

      {content.summary && <p className="post-card__caption">{content.summary}</p>}

      {shown.length > 0 && (
        <div className="post-card__grid">
          {shown.map((m, i) => (
            <div className="post-card__cell" key={i}>
              <img src={m.url} alt={m.alt_text ?? ''} loading="lazy" />
              {i === 3 && extra > 0 && (
                <span className="post-card__more">+{extra}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </article>
  )
}
