import type { ContentOut } from '../api/types'
import { MediaFrame } from './MediaFrame'
import './PostCard.css'

interface Props {
  content: ContentOut
  blurred?: boolean
  onClick?: () => void
}

function primary(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}

/** Thẻ bài viết ảnh/cộng đồng: media (+N nếu nhiều) + caption + meta. */
export function PostCard({ content, blurred, onClick }: Props) {
  const extra = content.media.length - 1
  return (
    <article
      className={blurred ? 'post-card post-card--blurred' : 'post-card'}
      onClick={onClick}
    >
      <div className="post-card__media">
        <MediaFrame media={primary(content)} ratio="4 / 5" />
        {extra > 0 && <span className="post-card__more">+{extra}</span>}
      </div>
      {content.summary && <p className="post-card__caption">{content.summary}</p>}
      <div className="post-card__meta">
        <span className="post-card__title">{content.title}</span>
        {content.published_at && (
          <time className="muted">
            {new Date(content.published_at).toLocaleDateString('vi-VN')}
          </time>
        )}
      </div>
    </article>
  )
}
