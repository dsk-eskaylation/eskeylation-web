import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AdminApiError,
  adminApi,
  type AdminUser,
  type ContentAdmin,
  type ContentMediaIn,
  type ContentStatus,
  type ContentType,
  type UserRole,
} from '../api/admin'
import { clearToken } from '../api/auth'
import { Modal } from '../components/Modal'
import './Cms.css'

const ROLES: { value: UserRole; label: string }[] = [
  { value: 'admin', label: 'Quản trị' },
  { value: 'editor', label: 'Biên tập' },
  { value: 'author', label: 'Tác giả' },
]

const ROLE_LABEL: Record<UserRole, string> = {
  admin: 'Quản trị',
  editor: 'Biên tập',
  author: 'Tác giả',
}

const TYPES: { value: ContentType; label: string }[] = [
  { value: 'music', label: 'Nhạc' },
  { value: 'gallery', label: 'Ảnh' },
  { value: 'community', label: 'Cộng đồng' },
  { value: 'homepage', label: 'Trang chủ' },
]

const STATUSES: { value: ContentStatus; label: string }[] = [
  { value: 'draft', label: 'Nháp' },
  { value: 'published', label: 'Đã đăng' },
  { value: 'archived', label: 'Lưu trữ' },
]

const STATUS_LABEL: Record<ContentStatus, string> = {
  draft: 'Nháp',
  published: 'Đã đăng',
  archived: 'Lưu trữ',
}

function typeLabel(t: ContentType) {
  return TYPES.find((x) => x.value === t)?.label ?? t
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

interface EditorMedia extends ContentMediaIn {
  url: string
}

/** Form tạo/sửa nội dung trong Modal. Music có field riêng; loại khác sửa body JSON. */
function Editor({
  initial,
  onClose,
  onSaved,
}: {
  initial: ContentAdmin | null // null = tạo mới
  onClose: () => void
  onSaved: () => void
}) {
  const [type, setType] = useState<ContentType>(initial?.type ?? 'music')
  const [title, setTitle] = useState(initial?.title ?? '')
  const [summary, setSummary] = useState(initial?.summary ?? '')
  const [artist, setArtist] = useState(
    typeof initial?.body.artist === 'string' ? initial.body.artist : '',
  )
  const [category, setCategory] = useState(
    typeof initial?.body.category === 'string' ? initial.body.category : '',
  )
  const [embedUrl, setEmbedUrl] = useState(
    typeof initial?.body.embed_url === 'string' ? initial.body.embed_url : '',
  )
  const [bodyJson, setBodyJson] = useState(
    JSON.stringify(initial?.body ?? {}, null, 2),
  )
  const [media, setMedia] = useState<EditorMedia[]>(
    (initial?.media ?? []).map((m) => ({
      media_id: m.media_id,
      url: m.url,
      position: m.position,
      is_primary: m.is_primary,
      caption: m.caption,
    })),
  )
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const isMusic = type === 'music'

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setError(null)
    setBusy(true)
    try {
      for (const file of Array.from(files)) {
        const up = await adminApi.uploadMedia(file)
        setMedia((prev) => [
          ...prev,
          {
            media_id: up.id,
            url: up.url,
            position: prev.length,
            is_primary: prev.length === 0,
          },
        ])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload lỗi')
    } finally {
      setBusy(false)
    }
  }

  const setPrimary = (id: number) =>
    setMedia((prev) => prev.map((m) => ({ ...m, is_primary: m.media_id === id })))

  const removeMedia = (id: number) =>
    setMedia((prev) =>
      prev
        .filter((m) => m.media_id !== id)
        .map((m, i) => ({ ...m, position: i })),
    )

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    let body: Record<string, unknown>
    if (isMusic) {
      body = { ...(initial?.body ?? {}) }
      body.artist = artist || undefined
      body.category = category || undefined
      body.embed_url = embedUrl || undefined
    } else {
      try {
        body = JSON.parse(bodyJson || '{}')
      } catch {
        setError('Body không phải JSON hợp lệ')
        return
      }
    }

    const payload = {
      title,
      summary: summary || null,
      body,
      media: media.map(({ media_id, position, is_primary, caption }) => ({
        media_id,
        position,
        is_primary,
        caption,
      })),
    }

    setBusy(true)
    try {
      if (initial) {
        await adminApi.update(initial.id, payload)
      } else {
        await adminApi.create({ ...payload, type })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal onClose={onClose}>
      <form className="cms-editor" onSubmit={onSubmit}>
        <h2 className="cms-editor__title">
          {initial ? `Sửa: ${initial.title}` : 'Nội dung mới'}
        </h2>

        {!initial && (
          <div className="cms-editor__types">
            {TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                className={
                  type === t.value ? 'cms-pill cms-pill--active' : 'cms-pill'
                }
                onClick={() => setType(t.value)}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        <label className="cms-field">
          <span>Tiêu đề</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
          />
        </label>

        <label className="cms-field">
          <span>Mô tả ngắn</span>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
          />
        </label>

        {isMusic ? (
          <>
            <div className="cms-editor__row">
              <label className="cms-field">
                <span>Nghệ sĩ</span>
                <input value={artist} onChange={(e) => setArtist(e.target.value)} />
              </label>
              <label className="cms-field">
                <span>Thể loại</span>
                <input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="LOVE RAP / GANGSTA / DISSIN' / AI"
                />
              </label>
            </div>
            <label className="cms-field">
              <span>Link video (YouTube/Vimeo)</span>
              <input
                value={embedUrl}
                onChange={(e) => setEmbedUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </label>
          </>
        ) : (
          <label className="cms-field">
            <span>Body (JSON)</span>
            <textarea
              className="cms-field__json"
              value={bodyJson}
              onChange={(e) => setBodyJson(e.target.value)}
              rows={8}
              spellCheck={false}
            />
          </label>
        )}

        <div className="cms-editor__media">
          <div className="cms-editor__media-head">
            <span>Media ({media.length})</span>
            <label className="cms-pill cms-editor__upload">
              + Tải ảnh/video
              <input
                type="file"
                accept="image/*,video/*"
                multiple
                onChange={(e) => {
                  void upload(e.target.files)
                  e.target.value = ''
                }}
              />
            </label>
          </div>
          {media.length > 0 && (
            <div className="cms-editor__thumbs">
              {media.map((m) => (
                <div
                  key={m.media_id}
                  className={
                    m.is_primary
                      ? 'cms-thumb cms-thumb--primary'
                      : 'cms-thumb'
                  }
                >
                  <img src={m.url} alt="" loading="lazy" />
                  <div className="cms-thumb__actions">
                    <button
                      type="button"
                      onClick={() => setPrimary(m.media_id)}
                      title="Đặt làm ảnh chính"
                    >
                      ★
                    </button>
                    <button
                      type="button"
                      onClick={() => removeMedia(m.media_id)}
                      title="Gỡ khỏi nội dung"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <p className="cms-error">
            <span>*</span>
            {error}
          </p>
        )}

        <div className="cms-editor__foot">
          <button type="button" className="cms-pill" onClick={onClose}>
            Huỷ
          </button>
          <button type="submit" className="cms-pill cms-pill--active" disabled={busy}>
            {busy ? 'Đang lưu…' : 'Lưu'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function fmtDay(iso: string) {
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

/** Form thêm tài khoản (Modal) — admin tạo trực tiếp, kích hoạt luôn. */
function NewUserForm({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('author')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Mật khẩu phải từ 8 ký tự')
      return
    }
    setBusy(true)
    try {
      await adminApi.createUser({ email, password, role })
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo tài khoản lỗi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal onClose={onClose}>
      <form className="cms-editor" onSubmit={onSubmit}>
        <h2 className="cms-editor__title">Thêm tài khoản</h2>
        <label className="cms-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="cms-field">
          <span>Mật khẩu (tối thiểu 8 ký tự)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        <div className="cms-field">
          <span>Vai trò</span>
          <div className="cms-editor__types">
            {ROLES.map((r) => (
              <button
                key={r.value}
                type="button"
                className={role === r.value ? 'cms-pill cms-pill--active' : 'cms-pill'}
                onClick={() => setRole(r.value)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        {error && (
          <p className="cms-error">
            <span>*</span>
            {error}
          </p>
        )}
        <div className="cms-editor__foot">
          <button type="button" className="cms-pill" onClick={onClose}>
            Huỷ
          </button>
          <button type="submit" className="cms-pill cms-pill--active" disabled={busy}>
            {busy ? 'Đang tạo…' : 'Tạo'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** Panel quản lý tài khoản (chỉ admin): duyệt tài khoản chờ, đổi vai trò, thêm mới. */
function UsersPanel({ meId }: { meId: number | null }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setUsers(await adminApi.listUsers())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải danh sách tài khoản lỗi')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thao tác lỗi')
    }
  }

  const pending = users.filter((u) => !u.is_active)
  const active = users.filter((u) => u.is_active)

  const renderRow = (u: AdminUser) => (
    <li key={u.id} className="cms__row page-enter">
      <div className="cms__row-main">
        <span className={u.is_active ? 'cms-badge cms-badge--published' : 'cms-badge cms-badge--draft'}>
          {u.is_active ? 'Hoạt động' : 'Chờ duyệt'}
        </span>
        <div className="cms__row-text">
          <span className="cms__row-title">{u.email}</span>
          <span className="cms__row-meta">
            {ROLE_LABEL[u.role]} · tạo {fmtDay(u.created_at)}
            {u.id === meId && ' · bạn'}
          </span>
        </div>
      </div>
      <div className="cms__row-actions">
        {!u.is_active && (
          <button
            type="button"
            className="cms-pill cms-pill--publish"
            onClick={() => void act(() => adminApi.updateUser(u.id, { is_active: true }))}
          >
            Duyệt
          </button>
        )}
        {/* Đổi vai trò — không cho tự đổi chính mình (server cũng chặn) */}
        {u.id !== meId &&
          ROLES.filter((r) => r.value !== u.role).map((r) => (
            <button
              key={r.value}
              type="button"
              className="cms-pill"
              onClick={() => void act(() => adminApi.updateUser(u.id, { role: r.value }))}
              title={`Đổi thành ${r.label}`}
            >
              → {r.label}
            </button>
          ))}
        {u.is_active && u.id !== meId && (
          <button
            type="button"
            className="cms-pill cms-pill--danger"
            onClick={() => {
              if (window.confirm(`Khoá tài khoản ${u.email}?`))
                void act(() => adminApi.updateUser(u.id, { is_active: false }))
            }}
          >
            Khoá
          </button>
        )}
      </div>
    </li>
  )

  return (
    <>
      <div className="cms__filters">
        <span className="cms__count">
          {users.length} tài khoản
          {pending.length > 0 && ` · ${pending.length} chờ duyệt`}
        </span>
        <button
          type="button"
          className="cms-pill cms-pill--new"
          onClick={() => setCreating(true)}
        >
          + Thêm tài khoản
        </button>
      </div>

      {error && (
        <p className="cms-error">
          <span>*</span>
          {error}
        </p>
      )}

      {loading ? (
        <p className="cms__status">Đang tải…</p>
      ) : (
        <>
          {pending.length > 0 && (
            <>
              <p className="cms__section-label">Chờ duyệt ({pending.length})</p>
              <ul className="cms__list">{pending.map(renderRow)}</ul>
            </>
          )}
          <p className="cms__section-label">Đang hoạt động ({active.length})</p>
          <ul className="cms__list">{active.map(renderRow)}</ul>
        </>
      )}

      {creating && (
        <NewUserForm
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            void load()
          }}
        />
      )}
    </>
  )
}

/** Trang CMS quản lý nội dung — list + filter + workflow + editor. */
export function Cms() {
  const navigate = useNavigate()
  const [me, setMe] = useState<AdminUser | null>(null)
  const [view, setView] = useState<'content' | 'users'>('content')
  const [type, setType] = useState<ContentType | null>(null)
  const [status, setStatus] = useState<ContentStatus | null>(null)
  const [items, setItems] = useState<ContentAdmin[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<ContentAdmin | null>(null)
  const [creating, setCreating] = useState(false)

  // Biết vai trò để hiện tab Tài khoản (chỉ admin)
  useEffect(() => {
    adminApi
      .me()
      .then(setMe)
      .catch((err) => {
        if (err instanceof AdminApiError && err.status === 401)
          navigate('/login', { replace: true })
      })
  }, [navigate])
  const isAdmin = me?.role === 'admin'

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const page = await adminApi.list({
        type: type ?? undefined,
        status: status ?? undefined,
      })
      setItems(page.items)
      setTotal(page.total)
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      setError(err instanceof Error ? err.message : 'Tải danh sách lỗi')
    } finally {
      setLoading(false)
    }
  }, [type, status, navigate])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
      await load()
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      setError(err instanceof Error ? err.message : 'Thao tác lỗi')
    }
  }

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className="cms">
      <header className="cms__topbar">
        <span className="cms__brand">
          ESKAYLATION <em>CMS</em>
        </span>
        <div className="cms__topbar-actions">
          {/* Chuyển view: Nội dung <-> Tài khoản (tab Tài khoản chỉ hiện cho admin) */}
          <button
            type="button"
            className={view === 'content' ? 'cms-pill cms-pill--active' : 'cms-pill'}
            onClick={() => setView('content')}
          >
            Nội dung
          </button>
          {isAdmin && (
            <button
              type="button"
              className={view === 'users' ? 'cms-pill cms-pill--active' : 'cms-pill'}
              onClick={() => setView('users')}
            >
              Tài khoản
            </button>
          )}
          <Link to="/" className="cms-pill">
            Xem trang
          </Link>
          <button type="button" className="cms-pill" onClick={logout}>
            Đăng xuất
          </button>
        </div>
      </header>

      {view === 'users' && isAdmin ? (
        <UsersPanel meId={me?.id ?? null} />
      ) : (
        <CmsContent
          type={type}
          setType={setType}
          status={status}
          setStatus={setStatus}
          items={items}
          total={total}
          loading={loading}
          error={error}
          act={act}
          onNew={() => setCreating(true)}
          onEdit={setEditing}
        />
      )}

      {(creating || editing) && (
        <Editor
          initial={editing}
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
          onSaved={() => {
            setCreating(false)
            setEditing(null)
            void load()
          }}
        />
      )}
    </div>
  )
}

interface CmsContentProps {
  type: ContentType | null
  setType: (t: ContentType | null) => void
  status: ContentStatus | null
  setStatus: (s: ContentStatus | null) => void
  items: ContentAdmin[]
  total: number
  loading: boolean
  error: string | null
  act: (fn: () => Promise<unknown>) => Promise<void>
  onNew: () => void
  onEdit: (c: ContentAdmin) => void
}

/** View quản lý nội dung (tách khỏi Cms để đọc dễ hơn). */
function CmsContent({
  type,
  setType,
  status,
  setStatus,
  items,
  total,
  loading,
  error,
  act,
  onNew,
  onEdit,
}: CmsContentProps) {
  return (
    <>
      <div className="cms__filters">
        <div className="cms__filter-group">
          <button
            type="button"
            className={type === null ? 'cms-pill cms-pill--active' : 'cms-pill'}
            onClick={() => setType(null)}
          >
            Tất cả
          </button>
          {TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              className={type === t.value ? 'cms-pill cms-pill--active' : 'cms-pill'}
              onClick={() => setType(type === t.value ? null : t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="cms__filter-group">
          {STATUSES.map((s) => (
            <button
              key={s.value}
              type="button"
              className={
                status === s.value ? 'cms-pill cms-pill--active' : 'cms-pill'
              }
              onClick={() => setStatus(status === s.value ? null : s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <button type="button" className="cms-pill cms-pill--new" onClick={onNew}>
          + Nội dung mới
        </button>
      </div>

      {error && (
        <p className="cms-error">
          <span>*</span>
          {error}
        </p>
      )}

      {loading ? (
        <p className="cms__status">Đang tải…</p>
      ) : items.length === 0 ? (
        <p className="cms__status">Chưa có nội dung nào.</p>
      ) : (
        <>
          <p className="cms__count">{total} nội dung</p>
          <ul className="cms__list">
            {items.map((c) => (
              <li key={c.id} className="cms__row page-enter">
                <div className="cms__row-main">
                  <span className={`cms-badge cms-badge--${c.status}`}>
                    {STATUS_LABEL[c.status]}
                  </span>
                  <div className="cms__row-text">
                    <span className="cms__row-title">{c.title}</span>
                    <span className="cms__row-meta">
                      {typeLabel(c.type)} · /{c.slug} · sửa {fmtTime(c.updated_at)}
                      {c.media.length > 0 && ` · ${c.media.length} media`}
                    </span>
                  </div>
                </div>
                <div className="cms__row-actions">
                  <button type="button" className="cms-pill" onClick={() => onEdit(c)}>
                    Sửa
                  </button>
                  {c.status !== 'published' ? (
                    <button
                      type="button"
                      className="cms-pill cms-pill--publish"
                      onClick={() => void act(() => adminApi.publish(c.id))}
                    >
                      Đăng
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="cms-pill"
                      onClick={() => void act(() => adminApi.unpublish(c.id))}
                    >
                      Gỡ
                    </button>
                  )}
                  {c.status !== 'archived' && (
                    <button
                      type="button"
                      className="cms-pill"
                      onClick={() => void act(() => adminApi.archive(c.id))}
                    >
                      Lưu trữ
                    </button>
                  )}
                  <button
                    type="button"
                    className="cms-pill"
                    onClick={() => void act(() => adminApi.duplicate(c.id))}
                  >
                    Nhân bản
                  </button>
                  <button
                    type="button"
                    className="cms-pill cms-pill--danger"
                    onClick={() => {
                      if (window.confirm(`Xoá "${c.title}"? Không hoàn tác được.`))
                        void act(() => adminApi.remove(c.id))
                    }}
                  >
                    Xoá
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}
