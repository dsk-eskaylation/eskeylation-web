import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AdminApiError,
  adminApi,
  type AdminUser,
  type BannedWord,
  type ContentAdmin,
  type ContentMediaIn,
  type ContentStatus,
  type ContentType,
  type UserRole,
} from '../api/admin'
import { logout as apiLogout } from '../api/auth'
import { Modal } from '../components/Modal'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import { Dashboard } from './Dashboard'
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
  { value: 'video', label: 'Video' },
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
  onSaved: (message?: string) => void
}) {
  const b = (initial?.body ?? {}) as Record<string, unknown>
  const bstr = (k: string) => (typeof b[k] === 'string' ? (b[k] as string) : '')

  const [type, setType] = useState<ContentType>(initial?.type ?? 'music')
  const [title, setTitle] = useState(initial?.title ?? '')
  const [summary, setSummary] = useState(initial?.summary ?? '')
  const [artist, setArtist] = useState(bstr('artist'))
  const [category, setCategory] = useState(bstr('category'))
  const [audioUrl, setAudioUrl] = useState(bstr('audio_url'))
  const [embedUrl, setEmbedUrl] = useState(bstr('embed_url'))
  const [author, setAuthor] = useState(bstr('author'))
  // Trang chủ: giới thiệu, các dòng "bảo trì", và các nhóm credits (vai trò + tên)
  const [intro, setIntro] = useState(bstr('intro'))
  const [maintainText, setMaintainText] = useState(
    Array.isArray(b.maintain) ? (b.maintain as string[]).join('\n') : '',
  )
  const [credits, setCredits] = useState<{ role: string; names: string }[]>(
    Array.isArray(b.credits)
      ? (b.credits as { role?: string; names?: string[] }[]).map((c) => ({
          role: c.role ?? '',
          names: Array.isArray(c.names) ? c.names.join(', ') : '',
        }))
      : [],
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

  // Cập nhật một nhóm credits của trang chủ
  const setCredit = (i: number, patch: Partial<{ role: string; names: string }>) =>
    setCredits((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)))

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

    // Dựng body từ các trường CỤ THỂ theo loại. Bắt đầu từ body cũ để KHÔNG
    // mất các khoá không hiển thị trên form (vd 'sections' của trang chủ).
    const body: Record<string, unknown> = { ...(initial?.body ?? {}) }
    const set = (k: string, v: string) => {
      if (v.trim()) body[k] = v.trim()
      else delete body[k]
    }
    if (type === 'music') {
      set('artist', artist)
      set('category', category)
      set('audio_url', audioUrl)
      set('embed_url', embedUrl)
    } else if (type === 'video') {
      set('artist', artist)
      set('embed_url', embedUrl)
    } else if (type === 'gallery' || type === 'community') {
      set('author', author)
    } else if (type === 'homepage') {
      set('intro', intro)
      const lines = maintainText
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
      if (lines.length) body.maintain = lines
      else delete body.maintain
      const cr = credits
        .map((c) => ({
          role: c.role.trim(),
          names: c.names
            .split(',')
            .map((n) => n.trim())
            .filter(Boolean),
        }))
        .filter((c) => c.role || c.names.length)
      if (cr.length) body.credits = cr
      else delete body.credits
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
        onSaved(`Đã cập nhật “${title}”`)
      } else {
        await adminApi.create({ ...payload, type })
        onSaved(`Đã tạo “${title}”`)
      }
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

        {type === 'music' && (
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
                <small className="cms-field__hint">
                  Dùng để nhóm bài theo dòng nhạc ở trang Nghe nhạc.
                </small>
              </label>
            </div>
            <label className="cms-field">
              <span>Link nhạc streaming (mp3/m4a)</span>
              <input
                value={audioUrl}
                onChange={(e) => setAudioUrl(e.target.value)}
                placeholder="https://.../bai-hat.mp3"
              />
              <small className="cms-field__hint">
                Có link này thì bài phát trực tuyến trong trình phát. Bỏ trống sẽ mở
                link video bên dưới.
              </small>
            </label>
            <label className="cms-field">
              <span>Link video (YouTube/Vimeo) — tùy chọn</span>
              <input
                value={embedUrl}
                onChange={(e) => setEmbedUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </label>
          </>
        )}

        {type === 'video' && (
          <>
            <label className="cms-field">
              <span>Nghệ sĩ</span>
              <input value={artist} onChange={(e) => setArtist(e.target.value)} />
            </label>
            <label className="cms-field">
              <span>Link video (YouTube/Vimeo) — bắt buộc để phát</span>
              <input
                value={embedUrl}
                onChange={(e) => setEmbedUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </label>
          </>
        )}

        {(type === 'gallery' || type === 'community') && (
          <label className="cms-field">
            <span>{type === 'gallery' ? 'Tác giả bộ ảnh' : 'Tên người đăng'}</span>
            <input value={author} onChange={(e) => setAuthor(e.target.value)} />
            <small className="cms-field__hint">
              {type === 'gallery'
                ? 'Hiện kèm ảnh khi người xem mở. Bỏ trống sẽ dùng tiêu đề.'
                : 'Tên hiển thị của tác giả bài đăng. Bỏ trống sẽ dùng tiêu đề.'}
            </small>
          </label>
        )}

        {type === 'homepage' && (
          <>
            <label className="cms-field">
              <span>Giới thiệu (đoạn “ESKAYLATION là gì?”)</span>
              <textarea
                value={intro}
                onChange={(e) => setIntro(e.target.value)}
                rows={3}
              />
            </label>
            <label className="cms-field">
              <span>Mục “Maintain Website” — mỗi dòng một mục</span>
              <textarea
                value={maintainText}
                onChange={(e) => setMaintainText(e.target.value)}
                rows={3}
                placeholder={'Quỹ: Forever Eskay\nNội dung CK: Fes'}
              />
            </label>
            <div className="cms-field">
              <span>Nhóm đóng góp (SHOUT OUT)</span>
              <small className="cms-field__hint">
                Mỗi nhóm gồm vai trò và danh sách tên (cách nhau bằng dấu phẩy).
              </small>
              <div className="cms-credits">
                {credits.map((c, i) => (
                  <div className="cms-credits__row" key={i}>
                    <input
                      className="cms-credits__role"
                      value={c.role}
                      onChange={(e) => setCredit(i, { role: e.target.value })}
                      placeholder="Vai trò (VD: DESIGN)"
                    />
                    <input
                      className="cms-credits__names"
                      value={c.names}
                      onChange={(e) => setCredit(i, { names: e.target.value })}
                      placeholder="Tên 1, Tên 2, …"
                    />
                    <button
                      type="button"
                      className="cms-credits__del"
                      onClick={() =>
                        setCredits((prev) => prev.filter((_, idx) => idx !== i))
                      }
                      aria-label="Xoá nhóm"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="cms-pill"
                  onClick={() =>
                    setCredits((prev) => [...prev, { role: '', names: '' }])
                  }
                >
                  + Thêm nhóm
                </button>
              </div>
            </div>
          </>
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
  onSaved: (message?: string) => void
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
      onSaved(`Đã thêm tài khoản ${email}`)
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
  const { notify } = useToast()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  // Tài khoản đang chờ xác nhận khoá (mở ConfirmDialog thay window.confirm)
  const [pendingLock, setPendingLock] = useState<AdminUser | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await adminApi.listUsers())
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Tải danh sách tài khoản lỗi', {
        tone: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<unknown>, success?: string) => {
    try {
      await fn()
      await load()
      if (success) notify(success, { tone: 'success' })
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', { tone: 'error' })
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
            onClick={() =>
              void act(
                () => adminApi.updateUser(u.id, { is_active: true }),
                `Đã duyệt ${u.email}`,
              )
            }
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
              onClick={() =>
                void act(
                  () => adminApi.updateUser(u.id, { role: r.value }),
                  `${u.email} → ${r.label}`,
                )
              }
              title={`Đổi thành ${r.label}`}
            >
              → {r.label}
            </button>
          ))}
        {u.is_active && u.id !== meId && (
          <button
            type="button"
            className="cms-pill cms-pill--danger"
            onClick={() => setPendingLock(u)}
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
          onSaved={(msg) => {
            setCreating(false)
            void load()
            if (msg) notify(msg, { tone: 'success' })
          }}
        />
      )}

      {pendingLock && (
        <ConfirmDialog
          title="Khoá tài khoản"
          message={`Khoá ${pendingLock.email}? Người này sẽ không đăng nhập được cho tới khi được mở lại.`}
          confirmLabel="Khoá"
          onConfirm={async () => {
            const u = pendingLock
            setPendingLock(null)
            await act(
              () => adminApi.updateUser(u.id, { is_active: false }),
              `Đã khoá ${u.email}`,
            )
          }}
          onClose={() => setPendingLock(null)}
        />
      )}
    </>
  )
}

/** Panel Kiểm duyệt (chỉ admin): hàng đợi bài CHỜ DUYỆT (nháp) + quản lý TỪ CẤM. */
function Moderation() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [pending, setPending] = useState<ContentAdmin[]>([])
  const [words, setWords] = useState<BannedWord[]>([])
  const [loading, setLoading] = useState(true)
  const [newWord, setNewWord] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [page, w] = await Promise.all([
        adminApi.list({ status: 'draft' }),
        adminApi.bannedWords(),
      ])
      setPending(page.items)
      setWords(w)
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      notify(err instanceof Error ? err.message : 'Tải dữ liệu lỗi', { tone: 'error' })
    } finally {
      setLoading(false)
    }
  }, [navigate, notify])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<unknown>, success?: string) => {
    try {
      await fn()
      await load()
      if (success) notify(success, { tone: 'success' })
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', { tone: 'error' })
    }
  }

  const addWord = async (e: FormEvent) => {
    e.preventDefault()
    const w = newWord.trim()
    if (!w) return
    await act(() => adminApi.addBannedWord(w), `Đã thêm từ cấm “${w}”`)
    setNewWord('')
  }

  return (
    <div className="cms-mod">
      {/* Hàng đợi chờ duyệt (nội dung nháp — cần admin duyệt trước khi công khai) */}
      <section>
        <p className="cms__section-label">Chờ duyệt ({pending.length})</p>
        <p className="cms-field__hint">
          Bài do biên tập viên / tác giả tạo nằm ở dạng nháp cho tới khi admin duyệt.
          Duyệt để đăng công khai, hoặc từ chối (chuyển lưu trữ).
        </p>
        {loading ? (
          <p className="cms__status">Đang tải…</p>
        ) : pending.length === 0 ? (
          <p className="cms__status">Không có bài nào chờ duyệt.</p>
        ) : (
          <ul className="cms__list">
            {pending.map((c) => (
              <li key={c.id} className="cms__row page-enter">
                <div className="cms__row-main">
                  <span className={`cms-badge cms-badge--${c.status}`}>
                    {STATUS_LABEL[c.status]}
                  </span>
                  <div className="cms__row-text">
                    <span className="cms__row-title">{c.title}</span>
                    <span className="cms__row-meta">
                      {typeLabel(c.type)}
                      {c.media.length > 0 && ` · ${c.media.length} media`} · tạo{' '}
                      {fmtTime(c.created_at)}
                      {c.author_email && ` · ${c.author_email}`}
                    </span>
                  </div>
                </div>
                <div className="cms__row-actions">
                  <button
                    type="button"
                    className="cms-pill cms-pill--publish"
                    onClick={() =>
                      void act(
                        () => adminApi.publish(c.id),
                        `Đã duyệt & đăng “${c.title}”`,
                      )
                    }
                  >
                    Duyệt &amp; đăng
                  </button>
                  <button
                    type="button"
                    className="cms-pill"
                    onClick={() =>
                      void act(
                        () => adminApi.archive(c.id),
                        `Đã từ chối “${c.title}” (chuyển lưu trữ)`,
                      )
                    }
                  >
                    Từ chối
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Từ cấm — chặn khi lưu mô tả/nội dung bài & khi gửi bình luận */}
      <section className="cms-mod__words">
        <p className="cms__section-label">Từ cấm ({words.length})</p>
        <p className="cms-field__hint">
          Mô tả / nội dung bài viết và bình luận chứa các từ này sẽ bị chặn khi
          lưu/gửi. So khớp không phân biệt hoa thường.
        </p>
        <form className="cms-mod__add" onSubmit={addWord}>
          <input
            value={newWord}
            onChange={(e) => setNewWord(e.target.value)}
            placeholder="Nhập từ cần cấm…"
            maxLength={100}
          />
          <button type="submit" className="cms-pill cms-pill--new">
            + Thêm
          </button>
        </form>
        <div className="cms-mod__chips">
          {words.length === 0 ? (
            <span className="cms__status">Chưa có từ cấm nào.</span>
          ) : (
            words.map((w) => (
              <span className="cms-chip" key={w.id}>
                {w.word}
                <button
                  type="button"
                  onClick={() =>
                    void act(
                      () => adminApi.removeBannedWord(w.id),
                      `Đã xoá từ “${w.word}”`,
                    )
                  }
                  aria-label={`Xoá từ ${w.word}`}
                >
                  ✕
                </button>
              </span>
            ))
          )}
        </div>
      </section>
    </div>
  )
}

/** Trang CMS quản lý nội dung — list + filter + workflow + editor. */
export function Cms() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [me, setMe] = useState<AdminUser | null>(null)
  const [view, setView] = useState<
    'content' | 'users' | 'dashboard' | 'moderation'
  >('content')
  const [type, setType] = useState<ContentType | null>(null)
  const [status, setStatus] = useState<ContentStatus | null>(null)
  const [items, setItems] = useState<ContentAdmin[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
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
      notify(err instanceof Error ? err.message : 'Tải danh sách lỗi', {
        tone: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [type, status, navigate, notify])

  useEffect(() => {
    void load()
  }, [load])

  /** Chạy một thao tác, reload danh sách, báo kết quả bằng toast.
      opts.success: nội dung toast thành công. opts.undo: hàm hoàn tác (hiện nút). */
  const act = async (
    fn: () => Promise<unknown>,
    opts?: { success?: string; undo?: () => Promise<unknown> },
  ) => {
    try {
      await fn()
      await load()
      if (opts?.success) {
        notify(opts.success, {
          tone: 'success',
          action: opts.undo
            ? {
                label: 'Hoàn tác',
                onClick: async () => {
                  await opts.undo!()
                  await load()
                  notify('Đã hoàn tác', { tone: 'info' })
                },
              }
            : undefined,
        })
      }
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', { tone: 'error' })
    }
  }

  const logout = async () => {
    await apiLogout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="cms">
      <header className="cms__topbar">
        <span className="cms__brand">
          ESKAYLATION <em>CMS</em>
        </span>
        <div className="cms__topbar-actions">
          {/* Tab Tổng quan/Tài khoản chỉ hiện cho admin; Nội dung cho mọi biên tập viên */}
          {isAdmin && (
            <button
              type="button"
              className={view === 'dashboard' ? 'cms-pill cms-pill--active' : 'cms-pill'}
              onClick={() => setView('dashboard')}
            >
              Tổng quan
            </button>
          )}
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
              className={
                view === 'moderation' ? 'cms-pill cms-pill--active' : 'cms-pill'
              }
              onClick={() => setView('moderation')}
            >
              Kiểm duyệt
            </button>
          )}
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
          <button type="button" className="cms-pill" onClick={() => void logout()}>
            Đăng xuất
          </button>
        </div>
      </header>

      {view === 'dashboard' && isAdmin ? (
        <Dashboard />
      ) : view === 'moderation' && isAdmin ? (
        <Moderation />
      ) : view === 'users' && isAdmin ? (
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
          onSaved={(msg) => {
            setCreating(false)
            setEditing(null)
            void load()
            if (msg) notify(msg, { tone: 'success' })
          }}
        />
      )}
    </div>
  )
}

interface ActOpts {
  success?: string
  undo?: () => Promise<unknown>
}

interface CmsContentProps {
  type: ContentType | null
  setType: (t: ContentType | null) => void
  status: ContentStatus | null
  setStatus: (s: ContentStatus | null) => void
  items: ContentAdmin[]
  total: number
  loading: boolean
  act: (fn: () => Promise<unknown>, opts?: ActOpts) => Promise<void>
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
  act,
  onNew,
  onEdit,
}: CmsContentProps) {
  // Nội dung đang chờ xác nhận xoá (mở ConfirmDialog thay window.confirm)
  const [pendingDelete, setPendingDelete] = useState<ContentAdmin | null>(null)
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
                      {c.author_email && ` · ${c.author_email}`}
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
                      onClick={() =>
                        void act(() => adminApi.publish(c.id), {
                          success: `Đã đăng “${c.title}”`,
                        })
                      }
                    >
                      Đăng
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="cms-pill"
                      onClick={() =>
                        void act(() => adminApi.unpublish(c.id), {
                          success: `Đã gỡ “${c.title}” về nháp`,
                          undo: () => adminApi.publish(c.id),
                        })
                      }
                    >
                      Gỡ
                    </button>
                  )}
                  {c.status !== 'archived' && (
                    <button
                      type="button"
                      className="cms-pill"
                      onClick={() =>
                        void act(() => adminApi.archive(c.id), {
                          success: `Đã lưu trữ “${c.title}”`,
                          // Hoàn tác: trả về trạng thái trước đó
                          undo: () =>
                            c.status === 'published'
                              ? adminApi.publish(c.id)
                              : adminApi.unpublish(c.id),
                        })
                      }
                    >
                      Lưu trữ
                    </button>
                  )}
                  <button
                    type="button"
                    className="cms-pill"
                    onClick={() =>
                      void act(() => adminApi.duplicate(c.id), {
                        success: `Đã nhân bản “${c.title}”`,
                      })
                    }
                  >
                    Nhân bản
                  </button>
                  <button
                    type="button"
                    className="cms-pill cms-pill--danger"
                    onClick={() => setPendingDelete(c)}
                  >
                    Xoá
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Xoá nội dung"
          message={`Xoá “${pendingDelete.title}”? Thao tác này KHÔNG hoàn tác được.`}
          confirmLabel="Xoá vĩnh viễn"
          onConfirm={async () => {
            const c = pendingDelete
            setPendingDelete(null)
            await act(() => adminApi.remove(c.id), {
              success: `Đã xoá “${c.title}”`,
            })
          }}
          onClose={() => setPendingDelete(null)}
        />
      )}
    </>
  )
}
