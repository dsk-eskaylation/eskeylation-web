import { useState } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { MediaFrame } from '../components/MediaFrame'
import { EmptyState } from '../components/EmptyState'
import './Music.css'

const CATEGORIES = ['LOVE RAP', 'GANGSTA', "DISSIN'", 'AI']

function primaryMedia(c: ContentOut) {
  return c.media.find((m) => m.is_primary) ?? c.media[0]
}

export function Music() {
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const state = useApi(
    () => api.list('music', { q: q || undefined, category: category || undefined }),
    [q, category],
  )

  const items = state.status === 'success' ? state.data.items : []
  const featured = items[0]
  const playlist = items.slice(1)

  return (
    <div className="music">
      <div className="music__topbar">
        <SearchBar value={q} onChange={setQ} placeholder="Tìm kiếm bài hát" />
        <div className="music__categories">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              className={category === c ? 'music__cat music__cat--active' : 'music__cat'}
              onClick={() => setCategory(category === c ? null : c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {state.status === 'loading' && <p className="muted">Đang tải…</p>}
      {state.status === 'error' && <EmptyState title="Không tải được nhạc." />}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState
          title="Chưa có nhạc"
          hint="Nội dung sẽ xuất hiện khi được xuất bản."
        />
      )}

      {featured && (
        <section className="music__stage">
          <div className="music__featured">
            <h2 className="music__title">{featured.title}</h2>
            <MediaFrame media={primaryMedia(featured)} />
          </div>

          {playlist.length > 0 && (
            <aside className="music__playlist" aria-label="Danh sách phát">
              {playlist.map((item) => (
                <button key={item.id} type="button" className="music__track">
                  <span className="music__track-thumb">
                    {primaryMedia(item) && (
                      <img src={primaryMedia(item)!.url} alt="" loading="lazy" />
                    )}
                  </span>
                  <span className="music__track-title">{item.title}</span>
                </button>
              ))}
            </aside>
          )}
        </section>
      )}
    </div>
  )
}
