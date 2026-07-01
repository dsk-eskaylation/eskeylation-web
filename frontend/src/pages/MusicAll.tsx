import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import type { ContentOut } from '../api/types'
import { SearchBar } from '../components/SearchBar'
import { MusicCard } from '../components/MusicCard'
import { VideoModal } from '../components/VideoModal'
import { EmptyState } from '../components/EmptyState'
import './MusicAll.css'

const CATEGORIES = ['LOVE RAP', 'GANGSTA', "DISSIN'", 'AI']

export function MusicAll() {
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [selected, setSelected] = useState<ContentOut | null>(null)
  const state = useApi(
    () =>
      api.list('music', {
        q: q || undefined,
        category: category || undefined,
        pageSize: 60,
      }),
    [q, category],
  )
  const items = state.status === 'success' ? state.data.items : []

  return (
    <div className="music-all">
      <header className="music-all__head">
        <Link to="/music" className="music-all__back">
          ‹ Quay về
        </Link>
        <div className="music-all__cats">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              className={
                category === c ? 'music-all__cat music-all__cat--active' : 'music-all__cat'
              }
              onClick={() => setCategory(category === c ? null : c)}
            >
              {c}
            </button>
          ))}
        </div>
        <SearchBar value={q} onChange={setQ} />
      </header>

      {state.status === 'loading' && <p className="muted">Đang tải…</p>}
      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Không tìm thấy bài hát" />
      )}

      <div className="music-all__grid">
        {items.map((item) => (
          <MusicCard key={item.id} content={item} onClick={() => setSelected(item)} />
        ))}
      </div>

      {selected && (
        <VideoModal content={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
