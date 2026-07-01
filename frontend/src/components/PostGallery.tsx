import type { ContentOut } from '../api/types'
import './PostGallery.css'

/** Nội dung modal xem bài đầy đủ: tất cả ảnh + caption. Dùng cho photos & community. */
export function PostGallery({ content }: { content: ContentOut }) {
  return (
    <div className="post-gallery">
      <h2 className="post-gallery__title">{content.title}</h2>
      {content.summary && <p className="post-gallery__caption">{content.summary}</p>}
      <div className="post-gallery__grid">
        {content.media.map((m, i) => (
          <img key={i} src={m.url} alt={m.alt_text ?? ''} loading="lazy" />
        ))}
      </div>
    </div>
  )
}
