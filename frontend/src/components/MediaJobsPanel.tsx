import { useCallback, useEffect, useRef, useState } from 'react'
import { adminApi, type MediaJobs } from '../api/admin'
import './MediaJobsPanel.css'

const labels: Record<string, string> = {
  skipped: 'Chưa xử lý', pending: 'Chờ xử lý', queued: 'Đã xếp hàng',
  processing: 'Đang xử lý', ready: 'Hoàn tất', failed: 'Cần thử lại',
}
const errors: Record<string, string> = {
  image_too_large: 'Ảnh vượt giới hạn xử lý 16 triệu pixel; file gốc vẫn dùng được.',
  video_too_large: 'Video vượt giới hạn xử lý 16 triệu pixel; file gốc vẫn dùng được.',
  invalid_media: 'Không đọc được file. Hãy kiểm tra hoặc tải lại file.',
  processor_unavailable: 'Bộ xử lý chưa sẵn sàng.',
  processing_timeout: 'File xử lý quá lâu.',
  worker_interrupted: 'Tác vụ đã bị gián đoạn nhiều lần.',
  processing_failed: 'Chưa xử lý được file; file gốc vẫn dùng được.',
}

export default function MediaJobsPanel() {
  const [data, setData] = useState<MediaJobs | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)
  const mounted = useRef(false)
  const loading = useRef(false)
  const refresh = useCallback(async () => {
    if (loading.current) return
    loading.current = true
    try {
      const result = await adminApi.mediaJobs()
      if (mounted.current) { setData(result); setError('') }
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Không tải được trạng thái xử lý')
    } finally { loading.current = false }
  }, [])
  useEffect(() => {
    mounted.current = true
    void refresh()
    const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, 15_000)
    return () => { mounted.current = false; window.clearInterval(timer) }
  }, [refresh])
  async function process(id: number) {
    if (busy !== null) return
    setBusy(id)
    try { await adminApi.processMedia(id); await refresh() }
    catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : 'Không gửi được yêu cầu') }
    finally { if (mounted.current) setBusy(null) }
  }
  return (
    <section className="media-jobs" aria-labelledby="media-jobs-title">
      <div className="media-jobs__heading">
        <h2 id="media-jobs-title">Xử lý ảnh và video</h2>
        <span role="status">{!data ? 'Đang kiểm tra…' : !data.enabled ? 'Chưa bật' : data.worker_online ? 'Đang hoạt động' : 'Tạm gián đoạn'}</span>
      </div>
      {error && <p role="alert">{error}</p>}
      {data && <>
        <p>Ảnh mới được tạo nhiều kích thước; video được tạo ảnh bìa. File gốc luôn được giữ lại.</p>
        <dl className="media-jobs__counts">{Object.entries(labels).map(([status, label]) => <div key={status}><dt>{label}</dt><dd>{data.counts[status] ?? 0}</dd></div>)}</dl>
        {!data.worker_online && data.enabled && <p role="status">Tác vụ đang được giữ lại và sẽ tiếp tục khi bộ xử lý hoạt động trở lại.</p>}
        <ul className="media-jobs__list">{data.items.map(item => <li key={item.id}>
          <div><strong>Media #{item.id}</strong> · {item.mime_type}<br /><span>{labels[item.processing_status] ?? item.processing_status} · {item.processing_attempts} lần xử lý</span>
            {item.processing_error_code && <p>{errors[item.processing_error_code] ?? 'Chưa xử lý được file.'}</p>}
          </div>
          {['skipped', 'failed'].includes(item.processing_status) && <button type="button" className="cms-pill" disabled={!data.enabled || busy !== null} onClick={() => void process(item.id)}>{busy === item.id ? 'Đang gửi…' : item.processing_status === 'failed' ? 'Thử lại' : 'Xử lý'}</button>}
        </li>)}</ul>
        {data.items.length === 20 && <p>Hiển thị 20 file gần đây chưa hoàn tất.</p>}
      </>}
    </section>
  )
}
