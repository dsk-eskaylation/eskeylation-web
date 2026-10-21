import { Link } from 'react-router-dom'

export function NotFound() {
  return <section className="not-found" aria-labelledby="not-found-title">
    <p className="muted">404</p>
    <h1 id="not-found-title">Không tìm thấy trang</h1>
    <p>Đường dẫn có thể đã thay đổi hoặc không còn tồn tại.</p>
    <div className="page-actions">
      <Link className="page-action" to="/">Về trang chủ</Link>
      <Link className="page-action" to="/music">Mở thư viện nhạc</Link>
    </div>
  </section>
}
