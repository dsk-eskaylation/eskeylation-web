import { api, type ListParams } from '../api/client'
import { useApi } from '../api/useApi'

interface Props {
  type: 'music' | 'photos' | 'community'
  title: string
  params?: ListParams
}

/** Trang list tạm cho music/photos/community — sẽ thay bằng UI đúng Figma ở Phase 4. */
export function ContentList({ type, title, params }: Props) {
  const state = useApi(() => api.list(type, params), [type])

  return (
    <section>
      <h1>{title}</h1>
      {state.status === 'loading' && <p className="muted">Đang tải…</p>}
      {state.status === 'error' && <p className="muted">Không tải được nội dung.</p>}
      {state.status === 'success' &&
        (state.data.items.length === 0 ? (
          <p className="muted">Chưa có nội dung.</p>
        ) : (
          <ul>
            {state.data.items.map((item) => (
              <li key={item.id}>{item.title}</li>
            ))}
          </ul>
        ))}
    </section>
  )
}
