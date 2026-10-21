import { EmptyState } from './EmptyState'

export function LibraryFeedback({ status, empty, query, noun, onRetry, onClear }: {
  status: 'loading' | 'success' | 'error'
  empty: boolean
  query: string
  noun: string
  onRetry: () => void
  onClear: () => void
}) {
  if (status === 'loading') return <p className="page-feedback" role="status">Đang tải {noun}…</p>
  if (status === 'error') return <div className="page-feedback" role="alert">
    <EmptyState title={`Chưa tải được ${noun}.`} hint="Kiểm tra kết nối mạng rồi thử lại." />
    <button type="button" className="page-action" onClick={onRetry}>Thử lại</button>
  </div>
  if (!empty) return null
  return <div className="page-feedback" role="status">
    <EmptyState title={query.trim() ? `Không tìm thấy ${noun} phù hợp.` : `Thư viện chưa có ${noun}.`} hint={query.trim() ? 'Hãy thử từ khóa khác hoặc xóa tìm kiếm.' : undefined} />
    {query && <button type="button" className="page-action" onClick={onClear}>Xóa tìm kiếm</button>}
  </div>
}
