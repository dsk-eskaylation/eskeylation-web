import type { ContentOut } from '../api/types'
import { Modal } from './Modal'
import './VideoModal.css'

/** Chuyển link youtube/vimeo sang dạng embed để nhúng iframe. */
function toEmbedUrl(url: string): string | null {
  try {
    const u = new URL(url)
    const host = u.hostname.replace(/^www\./, '')
    if (host === 'youtu.be') return `https://www.youtube.com/embed${u.pathname}`
    if (host === 'youtube.com') {
      const id = u.searchParams.get('v')
      return id ? `https://www.youtube.com/embed/${id}` : null
    }
    if (host.endsWith('vimeo.com')) {
      const id = u.pathname.split('/').filter(Boolean).pop()
      return id ? `https://player.vimeo.com/video/${id}` : null
    }
  } catch {
    return null
  }
  return null
}

function Player({ content }: { content: ContentOut }) {
  const embed =
    typeof content.body.embed_url === 'string'
      ? toEmbedUrl(content.body.embed_url)
      : null
  const videoMedia = content.media.find((m) => m.mime_type.startsWith('video/'))
  const poster = content.media.find((m) => m.is_primary) ?? content.media[0]

  if (embed) {
    return (
      <iframe
        className="video-modal__frame"
        src={embed}
        title={content.title}
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
      />
    )
  }
  if (videoMedia) {
    return (
      <video
        className="video-modal__frame"
        src={videoMedia.url}
        controls
        autoPlay
        poster={poster?.url}
      />
    )
  }
  return poster ? (
    <img className="video-modal__frame" src={poster.url} alt={content.title} />
  ) : (
    <div className="video-modal__frame video-modal__frame--empty" />
  )
}

/** Modal video (Figma "Nghe nhạc/ Khi đã chọn" #1:1675): không khung,
    header [TÊN BÀI — line — NGHỆ SĨ ......... X], video full width.
    Đóng (Escape/nút/nền) sẽ unmount player -> dừng phát. */
export function VideoModal({
  content,
  onClose,
}: {
  content: ContentOut
  onClose: () => void
}) {
  const artist = typeof content.body.artist === 'string' ? content.body.artist : 'DSK'
  return (
    <Modal onClose={onClose} variant="bare" showClose={false}>
      <div className="video-modal">
        <header className="video-modal__head">
          <div className="video-modal__meta">
            <h2 className="video-modal__title">{content.title.toUpperCase()}</h2>
            <svg viewBox="0 0 23 2" className="video-modal__line" aria-hidden="true">
              <line x1="0" y1="1" x2="23" y2="1" stroke="currentColor" />
            </svg>
            <span className="video-modal__artist">{artist.toUpperCase()}</span>
          </div>
          <button
            type="button"
            className="video-modal__close"
            onClick={onClose}
            aria-label="Đóng"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <line x1="5" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" />
              <line x1="19" y1="5" x2="5" y2="19" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
        </header>
        <Player content={content} />
      </div>
    </Modal>
  )
}
