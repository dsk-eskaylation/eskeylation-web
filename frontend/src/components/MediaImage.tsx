import { useState, type ImgHTMLAttributes } from 'react'
import type { MediaOut } from '../api/types'

type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'srcSet'> & {
  media: MediaOut
  original?: boolean
}

/** Bản phù hợp màn hình ở lưới; bản gốc khi xem lớn, không phóng thumbnail. */
export function MediaImage({ media, original = false, alt, sizes, ...props }: Props) {
  const [fallback, setFallback] = useState(false)
  const full = original || fallback
  const src = full ? media.original_url || media.url : media.url
  return (
    <img
      {...props}
      src={src}
      srcSet={full ? undefined : media.srcset || undefined}
      sizes={sizes ?? '(max-width: 640px) 100vw, (max-width: 1100px) 50vw, 33vw'}
      width={media.width ?? undefined}
      height={media.height ?? undefined}
      alt={alt ?? media.alt_text ?? ''}
      decoding="async"
      loading={props.loading ?? 'lazy'}
      onError={() => {
        if (!full && media.original_url) setFallback(true)
      }}
    />
  )
}
