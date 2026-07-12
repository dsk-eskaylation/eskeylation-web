import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AdminApiError,
  adminApi,
  type ActivityEntry,
  type ContentStatus,
  type ContentType,
  type DashboardStats,
} from '../api/admin'
import './Dashboard.css'

const REFRESH_MS = 15_000
const ACTIVITY_PAGE_SIZE = 20

/** Bộ lọc nhật ký theo loại thao tác. */
const ACTION_FILTERS: { value: string | null; label: string }[] = [
  { value: null, label: 'Tất cả' },
  { value: 'create', label: 'Tạo' },
  { value: 'update', label: 'Sửa' },
  { value: 'publish', label: 'Đăng' },
  { value: 'unpublish', label: 'Gỡ' },
  { value: 'archive', label: 'Lưu trữ' },
  { value: 'delete', label: 'Xoá' },
  { value: 'duplicate', label: 'Nhân bản' },
  { value: 'user_create', label: 'Thêm TK' },
  { value: 'user_update', label: 'Sửa TK' },
]

const TYPE_LABEL: Record<ContentType, string> = {
  music: 'Nhạc',
  video: 'Video',
  gallery: 'Ảnh',
  community: 'Cộng đồng',
  homepage: 'Trang chủ',
}

const STATUS_LABEL: Record<ContentStatus, string> = {
  draft: 'Nháp',
  published: 'Đã đăng',
  archived: 'Lưu trữ',
}

/** Hành động -> động từ tiếng Việt cho dòng nhật ký. */
const ACTION_VERB: Record<string, string> = {
  create: 'đã tạo',
  update: 'đã sửa',
  publish: 'đã đăng',
  unpublish: 'đã gỡ',
  archive: 'đã lưu trữ',
  delete: 'đã xoá',
  duplicate: 'đã nhân bản',
  user_create: 'đã thêm tài khoản',
  user_update: 'đã cập nhật tài khoản',
  banned_add: 'đã thêm từ cấm',
  banned_remove: 'đã xoá từ cấm',
  comment_delete: 'đã xoá bình luận',
}

const ACTION_TONE: Record<string, string> = {
  create: 'ok',
  publish: 'ok',
  duplicate: 'ok',
  user_create: 'ok',
  update: 'info',
  unpublish: 'warn',
  archive: 'warn',
  user_update: 'info',
  delete: 'danger',
  banned_add: 'ok',
  banned_remove: 'warn',
  comment_delete: 'danger',
}

const FIELD_LABEL: Record<string, string> = {
  title: 'tiêu đề',
  summary: 'mô tả',
  body: 'nội dung',
  media: 'media',
}

function formatBytes(n: number): string {
  if (n <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1)
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 10) return 'vừa xong'
  if (s < 60) return `${s} giây trước`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} phút trước`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} giờ trước`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d} ngày trước`
  const date = new Date(iso)
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`
}

/** Mô tả chi tiết bổ sung của một hành động (VD: "sửa: tiêu đề, media"). */
function activityDetail(e: ActivityEntry): string | null {
  if (e.action === 'update') {
    const parts: string[] = []
    // Diff tiêu đề cũ → mới (nếu có)
    const hasTitleDiff =
      typeof e.detail.title_from === 'string' && typeof e.detail.title_to === 'string'
    if (hasTitleDiff) {
      parts.push(`đổi tên: “${e.detail.title_from}” → “${e.detail.title_to}”`)
    }
    if (Array.isArray(e.detail.fields)) {
      const fields = (e.detail.fields as string[])
        .filter((f) => !(hasTitleDiff && f === 'title'))
        .map((f) => FIELD_LABEL[f] ?? f)
      if (fields.length) parts.push(`sửa: ${fields.join(', ')}`)
    }
    return parts.join(' · ') || null
  }
  if (e.action === 'user_update') {
    const parts: string[] = []
    if (e.detail.is_active === true) parts.push('duyệt / mở khoá')
    if (e.detail.is_active === false) parts.push('khoá')
    if (typeof e.detail.role === 'string') parts.push(`vai trò → ${e.detail.role}`)
    return parts.join(' · ') || null
  }
  if ((e.action === 'create' || e.action === 'delete') && typeof e.detail.type === 'string') {
    return TYPE_LABEL[e.detail.type as ContentType] ?? (e.detail.type as string)
  }
  return null
}

/** Ô số liệu: nhãn + số lớn + dòng phụ (breakdown). */
function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string | number
  sub?: React.ReactNode
  tone?: 'live' | 'ok' | 'warn'
}) {
  return (
    <div className={tone ? `dash-card dash-card--${tone}` : 'dash-card'}>
      <span className="dash-card__label">{label}</span>
      <span className="dash-card__value">{value}</span>
      {sub && <span className="dash-card__sub">{sub}</span>}
    </div>
  )
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [activity, setActivity] = useState<ActivityEntry[]>([])
  const [activityTotal, setActivityTotal] = useState(0)
  const [activityPage, setActivityPage] = useState(1)
  const [actionFilter, setActionFilter] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [auto, setAuto] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [lastAt, setLastAt] = useState<Date | null>(null)

  const onError = useCallback((err: unknown) => {
    if (err instanceof AdminApiError && err.status === 403) {
      setError('Chỉ quản trị viên mới xem được bảng điều khiển.')
    } else {
      setError(err instanceof Error ? err.message : 'Tải số liệu lỗi')
    }
  }, [])

  const loadStats = useCallback(async () => {
    setRefreshing(true)
    try {
      const s = await adminApi.stats()
      setStats(s)
      setLastAt(new Date())
      setError(null)
    } catch (err) {
      onError(err)
    } finally {
      setRefreshing(false)
    }
  }, [onError])

  const loadActivity = useCallback(
    async (page: number, filter: string | null, append: boolean) => {
      try {
        const a = await adminApi.activity(page, ACTIVITY_PAGE_SIZE, filter ?? undefined)
        setActivityTotal(a.total)
        setActivityPage(page)
        setActivity((prev) => (append ? [...prev, ...a.items] : a.items))
      } catch (err) {
        onError(err)
      }
    },
    [onError],
  )

  // Nạp lần đầu + mỗi khi đổi bộ lọc thao tác (reset về trang 1)
  useEffect(() => {
    void loadStats()
  }, [loadStats])
  useEffect(() => {
    void loadActivity(1, actionFilter, false)
  }, [actionFilter, loadActivity])

  // Tự làm mới: số liệu luôn cập nhật; nhật ký chỉ làm mới khi CHƯA bấm "Xem thêm"
  // (đang ở trang 1) để không phá vỡ danh sách người dùng đang xem.
  const refreshRef = useRef<() => void>(() => {})
  refreshRef.current = () => {
    void loadStats()
    if (activityPage === 1) void loadActivity(1, actionFilter, false)
  }
  useEffect(() => {
    if (!auto) return
    const id = setInterval(() => refreshRef.current(), REFRESH_MS)
    return () => clearInterval(id)
  }, [auto])

  const manualRefresh = () => {
    void loadStats()
    void loadActivity(1, actionFilter, false)
  }

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      await loadActivity(activityPage + 1, actionFilter, true)
    } finally {
      setLoadingMore(false)
    }
  }

  // Chỉ chặn toàn trang khi CHƯA có số liệu nào (lỗi tải lần đầu / 403)
  if (error && !stats) {
    return (
      <p className="cms-error">
        <span>*</span>
        {error}
      </p>
    )
  }

  if (!stats) {
    return <p className="cms__status">Đang tải số liệu…</p>
  }

  const s = stats
  const hasMore = activity.length < activityTotal
  return (
    <div className="dash">
      <div className="dash__bar">
        <div className="dash__live">
          <span className="dash__dot" aria-hidden="true" />
          {s.live_connections > 0
            ? `${s.live_connections} người đang xem trực tiếp`
            : 'Không có ai đang xem'}
        </div>
        <div className="dash__bar-right">
          {lastAt && (
            <span className="dash__updated">
              {refreshing ? 'Đang cập nhật…' : `Cập nhật ${lastAt.toLocaleTimeString('vi-VN')}`}
            </span>
          )}
          <button
            type="button"
            className={auto ? 'cms-pill cms-pill--active' : 'cms-pill'}
            onClick={() => setAuto((v) => !v)}
            title="Bật/tắt tự động làm mới mỗi 15 giây"
          >
            {auto ? '⏸ Tự làm mới' : '▶ Tự làm mới'}
          </button>
          <button type="button" className="cms-pill" onClick={manualRefresh}>
            ↻ Làm mới
          </button>
        </div>
      </div>

      <div className="dash__grid">
        <StatCard
          label="Tổng nội dung"
          value={s.content_total}
          sub={
            <>
              {STATUS_LABEL.published} {s.content_by_status.published} · {STATUS_LABEL.draft}{' '}
              {s.content_by_status.draft} · {STATUS_LABEL.archived}{' '}
              {s.content_by_status.archived}
            </>
          }
        />
        <StatCard
          label="Đăng trong 7 ngày"
          value={s.published_last_7d}
          tone={s.published_last_7d > 0 ? 'ok' : undefined}
          sub="nội dung mới xuất bản"
        />
        <StatCard
          label="Tài khoản"
          value={s.users_total}
          tone={s.users_pending > 0 ? 'warn' : undefined}
          sub={
            <>
              {s.users_active} hoạt động
              {s.users_pending > 0 && ` · ${s.users_pending} chờ duyệt`}
            </>
          }
        />
        <StatCard
          label="Media"
          value={s.media_count}
          sub={
            <>
              {formatBytes(s.media_size)} · {s.media_images} ảnh · {s.media_videos} video
            </>
          }
        />
        <StatCard
          label="Bình luận"
          value={s.comments_total}
          tone={s.comments_last_24h > 0 ? 'ok' : undefined}
          sub={`${s.comments_last_24h} trong 24 giờ`}
        />
        <StatCard
          label="Cảm xúc"
          value={s.reactions_total}
          sub={`${s.saved_total} lượt lưu bài`}
        />
        <StatCard
          label="Đang xem trực tiếp"
          value={s.live_connections}
          tone="live"
          sub="kết nối realtime"
        />
      </div>

      <div className="dash__breakdown">
        <span className="dash__breakdown-title">Nội dung theo loại</span>
        <div className="dash__bars">
          {(Object.keys(TYPE_LABEL) as ContentType[]).map((t) => {
            const n = s.content_by_type[t] ?? 0
            const pct = s.content_total ? Math.round((n / s.content_total) * 100) : 0
            return (
              <div className="dash__bar-row" key={t}>
                <span className="dash__bar-label">{TYPE_LABEL[t]}</span>
                <span className="dash__bar-track">
                  <span className="dash__bar-fill" style={{ width: `${pct}%` }} />
                </span>
                <span className="dash__bar-num">{n}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="dash__activity">
        <div className="dash__activity-head">
          <span className="dash__breakdown-title">Hoạt động gần đây</span>
          <span className="dash__activity-count">{activityTotal} bản ghi</span>
        </div>
        <div className="dash__activity-filters">
          {ACTION_FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              className={
                actionFilter === f.value ? 'cms-pill cms-pill--active' : 'cms-pill'
              }
              onClick={() => setActionFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        {activity.length === 0 ? (
          <p className="cms__status">Chưa có hoạt động nào khớp bộ lọc.</p>
        ) : (
          <ul className="dash__feed">
            {activity.map((e) => {
              const detail = activityDetail(e)
              return (
                <li className="dash__feed-item" key={e.id}>
                  <span
                    className={`dash__feed-dot dash__feed-dot--${ACTION_TONE[e.action] ?? 'info'}`}
                    aria-hidden="true"
                  />
                  <div className="dash__feed-text">
                    <span className="dash__feed-line">
                      <strong>{e.actor_email ?? 'Hệ thống'}</strong>{' '}
                      {ACTION_VERB[e.action] ?? e.action}{' '}
                      {e.entity_title && <em>“{e.entity_title}”</em>}
                    </span>
                    <span className="dash__feed-meta">
                      {relTime(e.created_at)}
                      {detail && ` · ${detail}`}
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        {hasMore && (
          <button
            type="button"
            className="cms-pill dash__more"
            onClick={() => void loadMore()}
            disabled={loadingMore}
          >
            {loadingMore ? 'Đang tải…' : 'Xem thêm'}
          </button>
        )}
      </div>
    </div>
  )
}
