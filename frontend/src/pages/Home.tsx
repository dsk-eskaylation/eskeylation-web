import { api } from '../api/client'
import { useApi } from '../api/useApi'

export function Home() {
  const state = useApi(() => api.homepage())

  if (state.status === 'loading') return <p className="muted">Đang tải…</p>
  if (state.status === 'error')
    return <p className="muted">Chưa có nội dung trang chủ.</p>

  const home = state.data
  const sections = Array.isArray(home.body.sections) ? home.body.sections : []

  return (
    <section className="home">
      <h1>{home.title}</h1>
      {home.summary && <p className="muted">{home.summary}</p>}
      <pre className="debug">{JSON.stringify(sections, null, 2)}</pre>
    </section>
  )
}
