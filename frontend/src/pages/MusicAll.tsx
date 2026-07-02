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

const CATEGORIES = ['LIFE RAP', 'LOVE RAP', 'GANGSTA', "DISSIN'", 'AI']

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
      {/* Header (Figma #1:1385): Quay về | pills | search */}
      <header className="music-all__head">
        <Link to="/music" className="music-all__back">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <polyline
              points="14,5 7,12 14,19"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
          </svg>
          Quay về
        </Link>

        <div className="music-all__cats">
          <button
            type="button"
            className={
              category === null
                ? 'music-all__cat music-all__cat--active'
                : 'music-all__cat'
            }
            onClick={() => setCategory(null)}
          >
            Tất cả
          </button>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              className={
                category === c
                  ? 'music-all__cat music-all__cat--active'
                  : 'music-all__cat'
              }
              onClick={() => setCategory(category === c ? null : c)}
            >
              {c}
            </button>
          ))}
        </div>

        <SearchBar value={q} onChange={setQ} onClear={() => setQ('')} />
      </header>

      {state.status === 'success' && items.length === 0 && (
        <EmptyState title="Hiện tại chưa có bài hát nào TT.  " />
      )}

      <div className="music-all__grid">
        {items.map((item, i) => (
          <div
            className="music-all__cell"
            key={item.id}
            style={{ animationDelay: `${(i % 9) * 60}ms` }}
          >
            <MusicCard content={item} onClick={() => setSelected(item)} />
          </div>
        ))}
      </div>

      {selected && <VideoModal content={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
