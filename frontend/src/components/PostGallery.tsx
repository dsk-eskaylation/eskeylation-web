import type { ContentOut } from '../api/types'
import './PostGallery.css'

function fmtDate(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')} . ${String(d.getMonth() + 1).padStart(2, '0')}. ${d.getFullYear()}`
}

/** Nội dung modal xem bài đầy đủ (Figma "Khi chọn xem full ảnh" EL-ef611fd5):
    header avatar + tên + ngày + caption, lưới ảnh 2 cột bo góc 10.
    Dùng chung cho photos & community. */
export function PostGallery({ content }: { content: ContentOut }) {
  const author =
    typeof content.body.author === 'string' ? content.body.author : content.title
  return (
    <div className="post-gallery">
      <header className="post-gallery__head">
        <span className="post-gallery__avatar" aria-hidden="true" />
        <div className="post-gallery__id">
          <span className="post-gallery__name">{author}</span>
          <div className="post-gallery__meta">
            <time>{fmtDate(content.published_at)}</time>
            <span className="post-gallery__dot" aria-hidden="true" />
            <span>Admin</span>
          </div>
        </div>
      </header>

      {content.summary && <p className="post-gallery__caption">{content.summary}</p>}

      <div className="post-gallery__grid">
        {content.media.map((m, i) => (
          <img key={i} src={m.url} alt={m.alt_text ?? ''} loading="lazy" />
        ))}
      </div>
    </div>
  )
}
