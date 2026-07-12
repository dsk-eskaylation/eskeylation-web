import type { ContentOut } from '../api/types'

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

/** Trình phát video INLINE (không modal): iframe nhúng youtube/vimeo qua
    body.embed_url, hoặc <video> cho media video, hoặc ảnh poster nếu chưa có
    nguồn phát. autoPlay=true khi user chủ động bấm phát. */
export function VideoPlayer({
  content,
  autoPlay = true,
}: {
  content: ContentOut
  autoPlay?: boolean
}) {
  const embed =
    typeof content.body.embed_url === 'string'
      ? toEmbedUrl(content.body.embed_url)
      : null
  const videoMedia = content.media.find((m) => m.mime_type.startsWith('video/'))
  const poster = content.media.find((m) => m.is_primary) ?? content.media[0]

  if (embed) {
    const src = autoPlay
      ? `${embed}${embed.includes('?') ? '&' : '?'}autoplay=1`
      : embed
    return (
      <iframe
        className="video-player__frame"
        src={src}
        title={content.title}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
      />
    )
  }
  if (videoMedia) {
    return (
      <video
        className="video-player__frame"
        src={videoMedia.url}
        controls
        autoPlay={autoPlay}
        poster={poster?.url}
      />
    )
  }
  return poster ? (
    <img className="video-player__frame" src={poster.url} alt={content.title} />
  ) : (
    <div className="video-player__frame video-player__frame--empty" />
  )
}
