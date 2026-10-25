import './EmbedDock.css'

interface Props {
  src: string
  title: string
  artist: string
  onClose: () => void
}

// YouTube/SoundCloud terms require the official player to stay visible, so it can't be hidden behind PlayerBar.
export function EmbedDock({ src, title, artist, onClose }: Props) {
  const soundcloud = src.startsWith('https://w.soundcloud.com/')
  return (
    <aside className="embed-dock" aria-label={`Đang phát ${title}`}>
      <header className="embed-dock__head">
        <span className="embed-dock__title">
          {title}
          <small>{artist}</small>
        </span>
        <button type="button" className="embed-dock__close" onClick={onClose} aria-label="Đóng trình phát">
          ×
        </button>
      </header>
      <iframe
        key={src}
        className={soundcloud ? 'embed-dock__frame' : 'embed-dock__frame embed-dock__frame--video'}
        src={src}
        title={`Trình phát ${title}`}
        allow="autoplay; encrypted-media; picture-in-picture"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    </aside>
  )
}
