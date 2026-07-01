import type { MediaOut } from '../api/types'
import './MediaFrame.css'

interface Props {
  media?: MediaOut
  ratio?: string
  rounded?: boolean
}

/** Khung media bo góc dùng chung (poster ảnh/video). Placeholder khi chưa có media. */
export function MediaFrame({ media, ratio = '16 / 9', rounded = true }: Props) {
  return (
    <div
      className={rounded ? 'media-frame media-frame--rounded' : 'media-frame'}
      style={{ aspectRatio: ratio }}
    >
      {media ? (
        <img src={media.url} alt={media.alt_text ?? ''} loading="lazy" />
      ) : (
        <div className="media-frame__placeholder" aria-hidden="true" />
      )}
    </div>
  )
}
