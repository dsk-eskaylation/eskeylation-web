import { toEmbedUrl } from '../utils/video'
import type { ContentOut } from '../api/types'
import { usePlayer } from '../player/PlayerContext'



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
  const music = usePlayer()
  const embed =
    typeof content.body.embed_url === 'string'
      ? toEmbedUrl(content.body.embed_url)
      : null
  const videoMedia = content.media.find((m) => m.mime_type.startsWith('video/'))
  const images = content.media.filter((m) => m.url && (m.mime_type.startsWith('image/') || m.preview_url))
  const poster = images.find((m) => m.is_primary) ?? images[0]

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
        src={videoMedia.stream_url || videoMedia.url}
        controls
        autoPlay={autoPlay}
        playsInline
        preload="metadata"
        onPlay={music.pause}
        poster={poster?.url || undefined}
      />
    )
  }
  return poster ? (
    <img className="video-player__frame" src={poster.url} alt={content.title} />
  ) : (
    <div className="video-player__frame video-player__frame--empty" />
  )
}
