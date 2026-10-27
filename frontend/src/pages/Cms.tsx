import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  AdminApiError,
  adminApi,
  type AdminUser,
  type AlbumAdmin,
  type BannedWord,
  type ContentAdmin,
  type ContentMediaIn,
  type ContentStatus,
  type ContentType,
  type LyricSuggestion,
  type LyricStatus,
  type UserRole,
} from '../api/admin'
import { logout as apiLogout } from '../api/auth'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { creditGroups, creditMember, type CreditMember, type CreditGroup } from '../homepage'
import { UnsavedChangesModal } from '../components/UnsavedChangesModal'
import { FormError } from '../components/FormError'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import { AlbumsPanel } from './CmsAlbums'
import { Dashboard } from './Dashboard'
import './Cms.css'

const ROLES: { value: UserRole; label: string }[] = [
  { value: 'member', label: 'Thành viên' },
  { value: 'admin', label: 'Quản trị' },
  { value: 'editor', label: 'Biên tập' },
  { value: 'author', label: 'Tác giả' },
]

const ROLE_LABEL: Record<UserRole, string> = {
  member: 'Thành viên',
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

const ADD_LABEL: Record<ContentType, string> = {
  music: '+ Thêm bài nhạc',
  video: '+ Thêm video',
  gallery: '+ Thêm album ảnh',
  community: '+ Thêm bài viết',
  homepage: '+ Thêm trang chủ',
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
  mime_type: string
  purpose?: 'avatar'
}

const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,image/gif'
const UPLOADS: Record<ContentType, { accept: string; label: string }> = {
  music: { accept: `${IMAGE_ACCEPT},audio/mpeg,.mp3`, label: 'Tải nhạc/ảnh bìa' },
  video: { accept: `${IMAGE_ACCEPT},video/mp4,video/webm`, label: 'Tải video/poster' },
  gallery: { accept: IMAGE_ACCEPT, label: 'Tải ảnh' },
  community: { accept: `${IMAGE_ACCEPT},video/mp4,video/webm`, label: 'Tải ảnh/video' },
  homepage: { accept: IMAGE_ACCEPT, label: 'Tải ảnh đầu trang' },
}

function CreditMemberFields({ member, label, media, busy, onChange, onUpload }: {
  member: CreditMember; label: string; media: EditorMedia[]; busy: boolean
  onChange: (member: CreditMember) => void
  onUpload: (files: FileList | null) => void
}) {
  const image = media.find((asset) => asset.media_id === member.media_id)
  return <div className="cms-credit-member">
    <label className="cms-field"><span>{label}</span>
      <input value={member.name} disabled={busy} maxLength={255} onChange={(event) => onChange({ ...member, name: event.target.value })} />
    </label>
    <ImageField image={image} label={label} alt={`Ảnh ${member.name || label}`} busy={busy}
      onUpload={onUpload} onRemove={() => onChange({ name: member.name })} />
  </div>
}

function ImageField({ image, label, alt, busy, onUpload, onRemove }: {
  image: EditorMedia | undefined; label: string; alt: string; busy: boolean
  onUpload: (files: FileList | null) => void
  onRemove: () => void
}) {
  return <div className="cms-credit-member__image">
    {image && <img src={image.url} alt={alt} />}
    <label className="cms-pill cms-editor__upload">{image ? 'Đổi ảnh' : 'Thêm ảnh'}
      <input type="file" aria-label={`Ảnh ${label}`} accept={IMAGE_ACCEPT} disabled={busy} onChange={(event) => { onUpload(event.target.files); event.target.value = '' }} />
    </label>
    {image && <button type="button" className="cms-pill" disabled={busy} onClick={onRemove}>Gỡ ảnh</button>}
  </div>
}

interface ProductForm { name: string; description: string; form_url: string; media_id?: number }
interface SupportForm { intro: string; amount: string; used: string; statements: string; qr_media_id?: number }

function section(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
const text = (value: unknown) => (typeof value === 'string' ? value : '')
const imageId = (value: unknown) => (typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : undefined)

/** Fields map to the public page for each content type. */
function Editor({
  initial,
  defaultType,
  onClose,
  onSaved,
}: {
  initial: ContentAdmin | null // null = tạo mới
  defaultType: ContentType
  onClose: () => void
  onSaved: (message?: string) => void
}) {
  const b = (initial?.body ?? {}) as Record<string, unknown>
  const bstr = (k: string) => (typeof b[k] === 'string' ? (b[k] as string) : '')

  const [type, setType] = useState<ContentType>(initial?.type ?? defaultType)
  const [title, setTitle] = useState(initial?.title ?? '')
  const [summary, setSummary] = useState(initial?.summary ?? '')
  const [artist, setArtist] = useState(bstr('artist'))
  const [audioUrl, setAudioUrl] = useState(bstr('audio_url'))
  const [lyrics, setLyrics] = useState(bstr('lyrics'))
  const [embedUrl, setEmbedUrl] = useState(bstr('embed_url'))
  const [albumId, setAlbumId] = useState(initial?.album_id ? String(initial.album_id) : '')
  const [trackNo, setTrackNo] = useState(initial?.track_no ? String(initial.track_no) : '')
  const [albumOptions, setAlbumOptions] = useState<AlbumAdmin[]>([])
  useEffect(() => {
    if (type !== 'music') return
    let alive = true
    void adminApi.albums()
      .then((albums) => {
        if (!alive) return
        setAlbumOptions(albums)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [type])
  const [sourceUrl, setSourceUrl] = useState(initial?.source_url ?? '')
  const [coverLink, setCoverLink] = useState(initial?.cover_url ?? '')
  const [lookup, setLookup] = useState<'idle' | 'busy' | string>('idle')
  const [author, setAuthor] = useState(bstr('author'))
  // Trang chủ: giới thiệu, các dòng "bảo trì", và các nhóm credits (vai trò + tên)
  const [intro, setIntro] = useState(bstr('intro'))
  const [maintainText, setMaintainText] = useState(
    Array.isArray(b.maintain) ? (b.maintain as string[]).join('\n') : '',
  )
  const [credits, setCredits] = useState<CreditGroup[]>(() => creditGroups(b.credits))
  const [leader, setLeader] = useState<CreditMember>(() =>
    creditMember(b.leader) ?? { name: Object.hasOwn(b, 'leader') ? '' : 'Cỏ nhỏ' })
  // Trang Cộng đồng (lưu trong body Trang chủ): lời mở đầu, sản phẩm, ủng hộ
  const [communityIntro, setCommunityIntro] = useState(bstr('community_intro'))
  const [communityRules, setCommunityRules] = useState(bstr('community_rules'))
  const [product, setProduct] = useState<ProductForm>(() => {
    const p = section(b.product)
    return { name: text(p.name), description: text(p.description), form_url: text(p.form_url), media_id: imageId(p.media_id) }
  })
  const [support, setSupport] = useState<SupportForm>(() => {
    const p = section(b.support)
    return {
      intro: text(p.intro), amount: text(p.amount), used: text(p.used), qr_media_id: imageId(p.qr_media_id),
      statements: Array.isArray(p.statements) ? p.statements.filter((u): u is string => typeof u === 'string').join('\n') : '',
    }
  })
  const originalAvatarIds = new Set([
    imageId(section(b.product).media_id),
    imageId(section(b.support).qr_media_id),
    creditMember(b.leader)?.media_id,
    ...creditGroups(b.credits).flatMap((group) => group.members.map((member) => member.media_id)),
  ])
  const [media, setMedia] = useState<EditorMedia[]>(
    (initial?.media ?? []).map((m) => ({
      media_id: m.media_id,
      url: m.url,
      mime_type: m.mime_type,
      position: m.position,
      is_primary: m.is_primary,
      caption: m.caption,
      purpose: originalAvatarIds.has(m.media_id) ? 'avatar' : undefined,
    })),
  )
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const draft = JSON.stringify({ type, title, summary, artist, audioUrl, lyrics, embedUrl, albumId, trackNo, sourceUrl, coverLink, author, intro, maintainText, credits, leader, communityIntro, communityRules, product, support, media })
  const [initialDraft] = useState(draft)

  // Cập nhật một nhóm credits của trang chủ
  const setCredit = (
    i: number,
    patch: Partial<CreditGroup>,
  ) =>
    setCredits((prev) =>
      prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    )

  const upload = async (files: FileList | null, avatar?: (member: number) => void) => {
    if (!files?.length) return
    setError(null)
    const allowed = avatar ? IMAGE_ACCEPT : UPLOADS[type].accept
    if (Array.from(files).some((file) => !allowed.split(',').includes(file.type))) {
      setError('Định dạng file không phù hợp với mục này. Hãy chọn đúng loại file được hướng dẫn.')
      return
    }
    setBusy(true)
    try {
      for (const file of Array.from(files)) {
        const up = await adminApi.uploadMedia(file)
        setMedia((prev) => [
          ...prev,
          {
            media_id: up.id,
            url: up.url,
            mime_type: up.mime_type,
            position: prev.length,
            is_primary: !avatar && !prev.some((asset) => !asset.purpose),
            purpose: avatar ? 'avatar' : undefined,
          },
        ])
        avatar?.(up.id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload lỗi')
    } finally {
      setBusy(false)
    }
  }

  const setPrimary = (id: number) =>
    setMedia((prev) =>
      prev.map((m) => ({ ...m, is_primary: m.media_id === id })),
    )

  const removeMedia = (id: number) =>
    setMedia((prev) =>
      prev
        .filter((m) => m.media_id !== id)
        .map((m, i) => ({ ...m, position: i })),
    )

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
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
      set('audio_url', audioUrl)
      set('lyrics', lyrics)
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
          members: c.members.filter((member) => member.name.trim()).map((member) => ({ ...member, name: member.name.trim() })),
        }))
        .filter((c) => c.role && c.members.length)
        .map((c) => ({ ...c, names: c.members.map((member) => member.name) }))
      if (cr.length) body.credits = cr
      else delete body.credits
      body.leader = leader.name.trim() ? { ...leader, name: leader.name.trim() } : null
      set('community_intro', communityIntro)
      set('community_rules', communityRules)
      const trimmed = (form: object) => Object.fromEntries(Object.entries(form)
        .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value])
        .filter(([, value]) => value !== '' && value !== undefined))
      const productBody = trimmed(product)
      if (Object.keys(productBody).length) body.product = productBody
      else delete body.product
      const { statements, ...supportFields } = support
      const supportBody = trimmed(supportFields)
      const links = statements.split('\n').map((line) => line.trim()).filter(Boolean)
      if (links.length) supportBody.statements = links
      if (Object.keys(supportBody).length) body.support = supportBody
      else delete body.support
      // New homepage forms must provide the sections required by publishing.
      // Existing structured sections are preserved when editing older records.
      if (!Array.isArray(body.sections) || body.sections.length === 0) {
        body.sections = [
          ...(intro.trim() ? [{ type: 'intro', text: intro.trim() }] : []),
          ...(leader.name.trim() ? [{ type: 'leader' }] : []),
          ...(media.some((asset) => !asset.purpose) ? [{ type: 'hero' }] : []),
          ...(cr.length ? [{ type: 'credits', groups: cr }] : []),
          ...(lines.length ? [{ type: 'support', items: lines }] : []),
        ]
      }
    }

    const savedTitle = type === 'homepage' ? initial?.title || 'Trang chủ' : title
    const avatarIds = new Set(type === 'homepage' ? [
      product.media_id,
      support.qr_media_id,
      ...(leader.name.trim() ? [leader.media_id] : []),
      ...credits.filter((group) => group.role.trim()).flatMap((group) => group.members.filter((member) => member.name.trim()).map((member) => member.media_id)),
    ] : [])
    const payload = {
      title: savedTitle,
      summary: summary || null,
      body,
      media: media.filter((m) => !m.purpose || avatarIds.has(m.media_id)).map(({ media_id, position, is_primary, caption }) => ({
        media_id,
        position,
        is_primary: !avatarIds.has(media_id) && is_primary,
        caption: caption?.trim() || null,
      })),
      ...(type === 'music'
        ? {
            source_url: sourceUrl.trim() || null,
            cover_url: coverLink.trim() || null,
            album_id: albumId ? Number(albumId) : null,
            track_no: albumId && trackNo ? Number(trackNo) : null,
          }
        : {}),
    }

    setBusy(true)
    try {
      if (initial) {
        await adminApi.update(initial.id, { ...payload, expected_updated_at: initial.updated_at })
        onSaved(`Đã cập nhật “${savedTitle}”`)
      } else {
        await adminApi.create({ ...payload, type })
        onSaved(`Đã tạo “${savedTitle}”`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại')
    } finally {
      setBusy(false)
    }
  }

  return (
    <UnsavedChangesModal onClose={onClose} dirty={draft !== initialDraft} busy={busy} label={initial ? `Sửa: ${initial.title}` : 'Nội dung mới'}>
      {(requestClose) => (
      <form className="cms-editor" onSubmit={onSubmit} aria-describedby={error ? 'cms-editor-error' : undefined} aria-busy={busy}>
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
                disabled={busy}
                aria-pressed={type === t.value}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {type !== 'homepage' && <label className="cms-field">
          <span>{type === 'music' ? 'Tên bài hát' : type === 'gallery' ? 'Tên bộ ảnh' : 'Tiêu đề'}</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
          />
        </label>}

        {(type === 'video' || type === 'community') && <label className="cms-field">
          <span>{type === 'community' ? 'Nội dung bài viết' : 'Mô tả ngắn'}</span>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
          />
        </label>}

        {type === 'music' && (
          <>
            <div className="cms-editor__row">
              <label className="cms-field">
                <span>Nghệ sĩ</span>
                <input
                  value={artist}
                  onChange={(e) => setArtist(e.target.value)}
                />
              </label>

            </div>
            <div className="cms-editor__row">
              <label className="cms-field">
                <span>Album</span>
                <select className="cms-field__select" value={albumId} onChange={(e) => setAlbumId(e.target.value)}>
                  <option value="">— Bài lẻ (không thuộc album) —</option>
                  {albumOptions.map((album) => (
                    <option key={album.id} value={album.id}>
                      {album.title}
                      {album.year ? ` (${album.year})` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label className="cms-field">
                <span>Số thứ tự trong album</span>
                <input
                  type="number"
                  min={1}
                  max={999}
                  value={trackNo}
                  onChange={(e) => setTrackNo(e.target.value)}
                  disabled={!albumId}
                />
              </label>
            </div>
            <div className="cms-field">
              <span id="cms-music-link-label">Link SoundCloud / YouTube (tùy chọn)</span>
              <div className="cms-field__inline">
                <input
                  id="cms-music-link"
                  aria-labelledby="cms-music-link-label"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://soundcloud.com/... hoặc https://youtu.be/..."
                />
                <button
                  type="button"
                  className="page-action"
                  disabled={!sourceUrl.trim() || lookup === 'busy'}
                  onClick={async () => {
                    setLookup('busy')
                    try {
                      const info = await adminApi.oembed(sourceUrl.trim())
                      if (!title.trim() && info.title) setTitle(info.title)
                      if (!artist.trim() && info.author) setArtist(info.author)
                      if (info.thumbnail_url) setCoverLink(info.thumbnail_url)
                      setLookup('idle')
                    } catch (err) {
                      setLookup(err instanceof Error ? err.message : 'Không lấy được thông tin bài')
                    }
                  }}
                >
                  {lookup === 'busy' ? 'Đang lấy…' : 'Lấy thông tin'}
                </button>
              </div>
              {lookup !== 'idle' && lookup !== 'busy' && (
                <small className="cms-field__hint" role="alert">{lookup}</small>
              )}
              <small className="cms-field__hint">
                Dán link là đăng được, không cần tải MP3. Bài phát bằng trình phát của SoundCloud/YouTube.
                Bấm “Lấy thông tin” để tự điền tên bài, nghệ sĩ (nếu đang trống) và ảnh bìa.
              </small>
              {coverLink && (
                <div className="cms-editor__row">
                  <img src={coverLink} alt="Ảnh bìa" width={64} height={64} style={{ objectFit: 'cover', borderRadius: 8 }} />
                  <button type="button" className="page-action" onClick={() => setCoverLink('')}>
                    Bỏ ảnh bìa
                  </button>
                </div>
              )}
            </div>
            <label className="cms-field">
              <span>Link nhạc có sẵn (tùy chọn)</span>
              <input
                value={audioUrl}
                onChange={(e) => setAudioUrl(e.target.value)}
                placeholder="https://.../bai-hat.mp3"
              />
              <small className="cms-field__hint">
                Tải file MP3 trong mục Media bên dưới để phát nhạc trên website.
                File đã tải lên được ưu tiên hơn link này.
              </small>
            </label>
            <label className="cms-field">
              <span id="cms-lyrics-label">Lời bài hát</span>
              <textarea
                aria-labelledby="cms-lyrics-label"
                value={lyrics}
                onChange={(e) => setLyrics(e.target.value)}
                rows={8}
                maxLength={8000}
              />
            </label>

          </>
        )}

        {type === 'video' && (
          <>
            <label className="cms-field">
              <span>Nghệ sĩ</span>
              <input
                value={artist}
                onChange={(e) => setArtist(e.target.value)}
              />
            </label>
            <label className="cms-field">
              <span>Link video (YouTube/Vimeo) — tùy chọn nếu đã tải video</span>
              <input
                value={embedUrl}
                onChange={(e) => setEmbedUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
              <small className="cms-field__hint">Tải file video trong mục Media hoặc nhập link YouTube/Vimeo để đăng.</small>
            </label>
          </>
        )}

        {(type === 'gallery' || type === 'community') && (
          <label className="cms-field">
            <span>
              {type === 'gallery' ? 'Tác giả bộ ảnh' : 'Tên người đăng'}
            </span>
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
              <span>Thông tin đóng góp — mỗi dòng một mục</span>
              <textarea
                value={maintainText}
                onChange={(e) => setMaintainText(e.target.value)}
                rows={3}
                placeholder={'Quỹ: Forever Eskay\nNội dung CK: Fes'}
              />
            </label>
            <div className="cms-field">
              <span>TRI ÂN</span>
              <small className="cms-field__hint">Mỗi người có tên và ảnh riêng. Bỏ trống ảnh để hiển thị chữ cái tên.</small>
              <CreditMemberFields member={leader} label="Tên Leader" media={media} busy={busy}
                onChange={setLeader} onUpload={(files) => void upload(files, (id) => setLeader((prev) => ({ ...prev, media_id: id })))} />
              <div className="cms-credits">
                {credits.map((group, i) => <fieldset className="cms-credit-group" key={i} disabled={busy}>
                  <legend>Nhóm {i + 1}</legend>
                  <div className="cms-credits__row">
                    <label className="cms-field"><span>Vai trò nhóm {i + 1}</span>
                      <input value={group.role} onChange={(event) => setCredit(i, { role: event.target.value })} placeholder="VD: DESIGN" required={group.members.some((member) => Boolean(member.name.trim()))} />
                    </label>
                    <button type="button" className="cms-pill" onClick={() => setCredits((prev) => prev.filter((_, index) => index !== i))}>Xoá nhóm {i + 1}</button>
                  </div>
                  {group.members.map((member, j) => <div className="cms-credit-person" key={j}>
                    <CreditMemberFields member={member} label={`Tên thành viên ${j + 1} nhóm ${i + 1}`} media={media} busy={busy}
                      onChange={(value) => setCredit(i, { members: group.members.map((person, index) => index === j ? value : person) })}
                      onUpload={(files) => void upload(files, (id) => setCredits((prev) => prev.map((entry, index) => index !== i ? entry : { ...entry, members: entry.members.map((person, index) => index === j ? { ...person, media_id: id } : person) })))} />
                    <button type="button" className="cms-pill" aria-label={`Xoá thành viên ${j + 1} nhóm ${i + 1}`} onClick={() => setCredit(i, { members: group.members.filter((_, index) => index !== j) })}>Xoá người</button>
                  </div>)}
                  <button type="button" className="cms-pill" onClick={() => setCredit(i, { members: [...group.members, { name: '' }] })}>+ Thêm người nhóm {i + 1}</button>
                </fieldset>)}
                <button type="button" className="cms-pill" disabled={busy} onClick={() => setCredits((prev) => [...prev, { role: '', members: [{ name: '' }] }])}>+ Thêm nhóm</button>
              </div>
            </div>
            <fieldset className="cms-credit-group" disabled={busy}>
              <legend>Trang Cộng đồng</legend>
              <label className="cms-field"><span>Lời mở đầu</span>
                <textarea value={communityIntro} onChange={(e) => setCommunityIntro(e.target.value)} rows={4} placeholder="Để trống để dùng lời mở đầu mặc định" />
              </label>
              <label className="cms-field"><span>Văn hóa cộng đồng</span>
                <textarea value={communityRules} onChange={(e) => setCommunityRules(e.target.value)} rows={2} placeholder="Yêu cầu tôn trọng, văn minh, hòa đồng" />
              </label>
              <small className="cms-field__hint">Sản phẩm: để trống tên thì trang hiện “Hiện không có sản phẩm nào”.</small>
              <label className="cms-field"><span>Tên sản phẩm</span>
                <input value={product.name} onChange={(e) => setProduct((prev) => ({ ...prev, name: e.target.value }))} maxLength={255} />
              </label>
              <label className="cms-field"><span>Mô tả sản phẩm</span>
                <textarea value={product.description} onChange={(e) => setProduct((prev) => ({ ...prev, description: e.target.value }))} rows={3} />
              </label>
              <label className="cms-field"><span>Link đăng ký mua (Google Form)</span>
                <input type="url" value={product.form_url} onChange={(e) => setProduct((prev) => ({ ...prev, form_url: e.target.value }))} placeholder="https://forms.gle/…" />
              </label>
              <ImageField image={media.find((asset) => asset.media_id === product.media_id)} label="sản phẩm" alt={`Ảnh ${product.name || 'sản phẩm'}`} busy={busy}
                onUpload={(files) => void upload(files, (id) => setProduct((prev) => ({ ...prev, media_id: id })))}
                onRemove={() => setProduct(({ media_id: _removed, ...rest }) => rest)} />
              <label className="cms-field"><span>Lời kêu gọi ủng hộ</span>
                <textarea value={support.intro} onChange={(e) => setSupport((prev) => ({ ...prev, intro: e.target.value }))} rows={2} />
              </label>
              <label className="cms-field"><span>Số tiền hiện tại</span>
                <input value={support.amount} onChange={(e) => setSupport((prev) => ({ ...prev, amount: e.target.value }))} placeholder="1.800.000" />
              </label>
              <label className="cms-field"><span>Đã sử dụng (số tiền và mục đích)</span>
                <textarea value={support.used} onChange={(e) => setSupport((prev) => ({ ...prev, used: e.target.value }))} rows={2} placeholder="Đã sử dụng … VNĐ với mục đích …" />
              </label>
              <ImageField image={media.find((asset) => asset.media_id === support.qr_media_id)} label="mã QR ủng hộ" alt="Mã QR ủng hộ" busy={busy}
                onUpload={(files) => void upload(files, (id) => setSupport((prev) => ({ ...prev, qr_media_id: id })))}
                onRemove={() => setSupport(({ qr_media_id: _removed, ...rest }) => rest)} />
              <label className="cms-field"><span>Sao kê — link bài Facebook, mỗi dòng một link</span>
                <textarea value={support.statements} onChange={(e) => setSupport((prev) => ({ ...prev, statements: e.target.value }))} rows={3} placeholder="https://www.facebook.com/…" />
              </label>
            </fieldset>
          </>
        )}

        <div className="cms-editor__media">
          {type === 'homepage' && <p className="cms-field__hint">Ảnh tải lên sẽ thay dải ảnh đầu trang. Nếu không có ảnh, website dùng bộ ảnh mặc định.</p>}
          <div className="cms-editor__media-head">
            <span>{type === 'homepage' ? 'Ảnh đầu trang' : type === 'music' ? 'Âm thanh và ảnh bìa' : 'Media'} ({media.filter((m) => !m.purpose).length})</span>
            <label className="cms-pill cms-editor__upload">
              + {UPLOADS[type].label}
              <input
                type="file"
                accept={UPLOADS[type].accept}
                disabled={busy}
                multiple
                onChange={(e) => {
                  void upload(e.target.files)
                  e.target.value = ''
                }}
              />
            </label>
          </div>
          {media.some((m) => !m.purpose) && (
            <div className="cms-editor__thumbs">
              {media.filter((m) => !m.purpose).map((m, index) => (
                <div className="cms-media-item" key={m.media_id}>
                <div
                  className={
                    m.is_primary ? 'cms-thumb cms-thumb--primary' : 'cms-thumb'
                  }
                >
                  {m.mime_type.startsWith('audio/') ? (
                    <audio src={m.url} controls preload="none" aria-label="Nghe thử nhạc" />
                  ) : m.mime_type.startsWith('video/') ? (
                    <video src={m.url} controls preload="metadata" aria-label="Xem thử video" />
                  ) : (
                    <img src={m.url} alt="" loading="lazy" />
                  )}
                  <div className="cms-thumb__actions">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setPrimary(m.media_id)}
                      title="Đặt làm media chính"
                    >
                      ★
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => removeMedia(m.media_id)}
                      title="Gỡ khỏi nội dung"
                    >
                      ✕
                    </button>
                  </div>
                </div>
                {type === 'gallery' && <label className="cms-field">
                  <span>Chú thích ảnh {index + 1}</span>
                  <textarea aria-label={`Chú thích ảnh ${index + 1}`} rows={2} value={m.caption ?? ''} onChange={(event) => setMedia((prev) => prev.map((asset) => asset.media_id === m.media_id ? { ...asset, caption: event.target.value } : asset))} />
                </label>}
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <FormError id="cms-editor-error" message={error} className="cms-error" />
        )}

        <div className="cms-editor__foot">
          <button type="button" className="cms-pill" onClick={requestClose} disabled={busy}>
            Huỷ
          </button>
          <button
            type="submit"
            className="cms-pill cms-pill--active"
            disabled={busy}
          >
            {busy ? 'Đang lưu…' : 'Lưu'}
          </button>
        </div>
      </form>
      )}
    </UnsavedChangesModal>
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
  const [role, setRole] = useState<UserRole>('member')
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
    <UnsavedChangesModal onClose={onClose} dirty={Boolean(email || password || role !== 'member')} busy={busy} label="Thêm tài khoản">
      {(requestClose) => (
      <form className="cms-editor" onSubmit={onSubmit} aria-describedby={error ? 'cms-user-error' : undefined} aria-busy={busy}>
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
                className={
                  role === r.value ? 'cms-pill cms-pill--active' : 'cms-pill'
                }
                onClick={() => setRole(r.value)}
                aria-pressed={role === r.value}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        {error && (
          <FormError id="cms-user-error" message={error} className="cms-error" />
        )}
        <div className="cms-editor__foot">
          <button type="button" className="cms-pill" onClick={requestClose} disabled={busy}>
            Huỷ
          </button>
          <button
            type="submit"
            className="cms-pill cms-pill--active"
            disabled={busy}
          >
            {busy ? 'Đang tạo…' : 'Tạo'}
          </button>
        </div>
      </form>
      )}
    </UnsavedChangesModal>
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
      notify(
        err instanceof Error ? err.message : 'Tải danh sách tài khoản lỗi',
        {
          tone: 'error',
        },
      )
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
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', {
        tone: 'error',
      })
    }
  }

  const pending = users.filter((u) => !u.is_active)
  const active = users.filter((u) => u.is_active)

  const renderRow = (u: AdminUser) => (
    <li key={u.id} className="cms__row page-enter">
      <div className="cms__row-main">
        <span
          className={
            u.is_active
              ? 'cms-badge cms-badge--published'
              : 'cms-badge cms-badge--draft'
          }
        >
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

function LyricsModeration() {
  const { notify } = useToast()
  const [items, setItems] = useState<LyricSuggestion[]>([])
  const [status, setStatus] = useState<LyricStatus>('pending')
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<{ item: LyricSuggestion; status: 'accepted' | 'rejected' } | null>(null)
  const generation = useRef(0)
  const load = useCallback(async () => {
    const request = ++generation.current
    setLoading(true)
    setError(null)
    try {
      const data = await adminApi.lyrics(page, status)
      if (request !== generation.current) return
      setItems(data.items)
      setTotal(data.total)
      setPages(Math.max(1, data.pages))
      if (page > Math.max(1, data.pages)) setPage(Math.max(1, data.pages))
    } catch (err) {
      if (request === generation.current) setError(err instanceof Error ? err.message : 'Không tải được lời nhạc')
    } finally {
      if (request === generation.current) setLoading(false)
    }
  }, [page, status])
  useEffect(() => { void load() }, [load])

  const review = async () => {
    if (!confirm || busy) return
    setBusy(true)
    try {
      await adminApi.reviewLyrics(confirm.item.id, confirm.status)
      setConfirm(null)
      notify(confirm.status === 'accepted' ? 'Đã duyệt và cập nhật lời bài hát' : 'Đã từ chối đóng góp', { tone: 'success' })
      await load()
    } catch (err) {
      setConfirm(null)
      notify(err instanceof Error ? err.message : 'Duyệt lời nhạc thất bại', { tone: 'error' })
      await load()
    } finally { setBusy(false) }
  }

  return (
    <section className="cms-lyrics" aria-label="Duyệt lời nhạc">
      <p className="cms__section-label">Đóng góp lời nhạc ({total})</p>
      <div className="cms-seg" role="group" aria-label="Trạng thái lời nhạc">
        {([['pending', 'Chờ duyệt'], ['accepted', 'Đã duyệt'], ['rejected', 'Đã từ chối']] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={status === value ? 'cms-seg__btn cms-seg__btn--on' : 'cms-seg__btn'}
            aria-pressed={status === value}
            disabled={busy}
            onClick={() => {
              setStatus(value)
              setPage(1)
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {error ? <p className="cms-error" role="alert">{error} <button type="button" className="cms-pill" onClick={() => void load()}>Thử lại</button></p>
        : loading ? <p className="cms__status">Đang tải lời nhạc…</p>
        : items.length === 0 ? <p className="cms__status">Không có đóng góp trong mục này.</p>
        : items.map((item) => (
          <article key={item.id} className="cms-lyrics__item">
            <h3>{item.title ?? `Bài hát #${item.content_id}`}</h3>
            <p className="cms__row-meta">{item.user_email ?? 'Tài khoản đã xóa'} · {fmtTime(item.created_at)}</p>
            <pre className="cms-lyrics__body">{item.body}</pre>
            {!item.can_accept && <p className="cms-field__hint">Bài hát chưa liên kết với CMS hoặc đã bị xóa; chưa thể duyệt.</p>}
            {item.status === 'pending' && <div className="cms__row-actions">
              <button type="button" className="cms-pill cms-pill--publish" disabled={busy || !item.can_accept} onClick={() => setConfirm({ item, status: 'accepted' })}>Duyệt lời nhạc</button>
              <button type="button" className="cms-pill" disabled={busy} onClick={() => setConfirm({ item, status: 'rejected' })}>Từ chối lời nhạc</button>
            </div>}
          </article>
        ))}
      <CmsPagination page={page} pages={pages} onChange={setPage} label="Phân trang lời nhạc" />
      {confirm && <ConfirmDialog
        title={confirm.status === 'accepted' ? 'Duyệt lời nhạc' : 'Từ chối lời nhạc'}
        message={confirm.status === 'accepted' ? `Thay lời hiện tại của “${confirm.item.title}” bằng đóng góp này?` : 'Từ chối đóng góp này? Lời bài hát hiện tại được giữ nguyên.'}
        confirmLabel={busy ? 'Đang xử lý…' : confirm.status === 'accepted' ? 'Duyệt và cập nhật' : 'Xác nhận từ chối'}
        onConfirm={review}
        onClose={() => { if (!busy) setConfirm(null) }}
      />}
    </section>
  )
}

/** Panel Kiểm duyệt (chỉ admin): lời nhạc, bài nháp và từ cấm. */
function Moderation() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [pending, setPending] = useState<ContentAdmin[]>([])
  const [words, setWords] = useState<BannedWord[]>([])
  const [loading, setLoading] = useState(true)
  const [newWord, setNewWord] = useState('')
  const [pageNumber, setPageNumber] = useState(1)
  const [pages, setPages] = useState(1)
  const [total, setTotal] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [page, w] = await Promise.all([
        adminApi.list({ status: 'draft', page: pageNumber }),
        adminApi.bannedWords(),
      ])
      setPending(page.items)
      setPages(Math.max(1, page.pages))
      setTotal(page.total)
      if (pageNumber > Math.max(1, page.pages))
        setPageNumber(Math.max(1, page.pages))
      setWords(w)
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      notify(err instanceof Error ? err.message : 'Tải dữ liệu lỗi', {
        tone: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [navigate, notify, pageNumber])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (fn: () => Promise<unknown>, success?: string) => {
    try {
      await fn()
      await load()
      if (success) notify(success, { tone: 'success' })
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', {
        tone: 'error',
      })
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
      <LyricsModeration />
      {/* Hàng đợi chờ duyệt (nội dung nháp — cần admin duyệt trước khi công khai) */}
      <section>
        <p className="cms__section-label">Chờ duyệt ({total})</p>
        <p className="cms-field__hint">
          Bài do biên tập viên / tác giả tạo nằm ở dạng nháp cho tới khi admin
          duyệt. Duyệt để đăng công khai, hoặc từ chối (chuyển lưu trữ).
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

      <CmsPagination
        page={pageNumber}
        pages={pages}
        onChange={setPageNumber}
        label="Phân trang chờ duyệt"
      />

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
  const source = useApi(() => api.homepage(), [])
  const navigate = useNavigate()
  const { notify } = useToast()
  const [me, setMe] = useState<AdminUser | null>(null)
  const [params, setParams] = useSearchParams()
  const isAdmin = me?.role === 'admin'
  const canManageAlbums = isAdmin || me?.role === 'editor'
  const requestedView = params.get('tab')
  const view =
    isAdmin && (requestedView === 'users' || requestedView === 'dashboard' || requestedView === 'moderation')
      ? requestedView
      : canManageAlbums && requestedView === 'albums'
        ? 'albums'
        : 'content'
  const type = TYPES.find((item) => item.value === params.get('type'))?.value ?? 'music'
  const status = STATUSES.find((item) => item.value === params.get('status'))?.value ?? null
  const requestedPage = Number(params.get('page') ?? 1)
  const pageNumber = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const updateParams = useCallback((patch: Record<string, string | null>, replace = false) => {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      Object.entries(patch).forEach(([key, value]) => { if (value === null) next.delete(key); else next.set(key, value) })
      return next
    }, { replace })
  }, [setParams])
  const setView = (value: string) => updateParams({ tab: value === 'content' ? null : value })
  const [navOpen, setNavOpen] = useState(false)
  const sideRef = useRef<HTMLElement>(null)
  const menuRef = useRef<HTMLButtonElement>(null)
  const closeNav = () => {
    setNavOpen(false)
    menuRef.current?.focus()
  }
  useEffect(() => {
    if (!navOpen) return
    sideRef.current?.querySelector<HTMLElement>('.cms-side__link')?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setNavOpen(false)
      menuRef.current?.focus()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [navOpen])
  const viewItem = (id: string, label: string) => ({
    key: id,
    label,
    active: view === id,
    go: () => setView(id),
  })
  const typeItem = (t: { value: ContentType; label: string }) => ({
    key: t.value,
    label: t.label,
    active: view === 'content' && type === t.value,
    go: () => updateParams({ tab: null, type: t.value, status: null, page: null }),
  })
  const [musicType, ...otherTypes] = TYPES
  const navGroups = [
    { label: null, items: isAdmin ? [viewItem('dashboard', 'Tổng quan')] : [] },
    {
      label: 'Nội dung',
      items: [
        typeItem(musicType),
        ...(canManageAlbums ? [viewItem('albums', 'Album')] : []),
        ...otherTypes.map(typeItem),
      ],
    },
    {
      label: 'Hệ thống',
      items: isAdmin ? [viewItem('moderation', 'Kiểm duyệt'), viewItem('users', 'Tài khoản')] : [],
    },
  ].filter((group) => group.items.length > 0)
  const pageTitle =
    view === 'content'
      ? typeLabel(type)
      : navGroups.flatMap((group) => group.items).find((item) => item.active)?.label ?? 'Nội dung'
  const setStatus = (value: ContentStatus | null) => updateParams({ status: value, page: null })
  const setPageNumber = useCallback((value: number) => updateParams({ page: value <= 1 ? null : String(value) }), [updateParams])
  const [items, setItems] = useState<ContentAdmin[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ContentAdmin | null>(null)
  const [creating, setCreating] = useState(false)
  const [pages, setPages] = useState(1)
  const loadGeneration = useRef(0)

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

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current
    setLoading(true)
    try {
      const page = await adminApi.list({
        type,
        status: status ?? undefined,
        page: pageNumber,
      })
      if (generation !== loadGeneration.current) return
      setItems(page.items)
      setTotal(page.total)
      setPages(Math.max(1, page.pages))
      if (pageNumber > Math.max(1, page.pages))
        setPageNumber(Math.max(1, page.pages))
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        navigate('/login', { replace: true })
        return
      }
      notify(err instanceof Error ? err.message : 'Tải danh sách lỗi', {
        tone: 'error',
      })
    } finally {
      if (generation === loadGeneration.current) setLoading(false)
    }
  }, [type, status, navigate, notify, pageNumber, setPageNumber])

  useEffect(() => {
    if (view === 'content') void load()
  }, [load, view])

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
      notify(err instanceof Error ? err.message : 'Thao tác lỗi', {
        tone: 'error',
      })
    }
  }

  const logout = async () => {
    try {
      await apiLogout()
      navigate('/login', { replace: true })
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Chưa đăng xuất được. Hãy thử lại.', { tone: 'error' })
    }
  }

  return (
    <div className={navOpen ? 'cms cms--nav-open' : 'cms'}>
      <a className="skip-link" href="#cms-main">Bỏ qua điều hướng quản trị</a>
      <aside className="cms-side" aria-label="Điều hướng quản trị" ref={sideRef}>
        <span className="cms__brand">
          ESKAYLATION <em>CMS</em>
        </span>
        <nav className="cms-side__nav">
          {navGroups.map((group) => (
            <div key={group.label ?? 'top'} className="cms-side__group">
              {group.label && <span className="cms-side__heading">{group.label}</span>}
              {group.items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={item.active ? 'cms-side__link cms-side__link--on' : 'cms-side__link'}
                  aria-current={item.active ? 'page' : undefined}
                  onClick={() => {
                    item.go()
                    setNavOpen(false)
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="cms-side__foot">
          {me && (
            <span className="cms-side__me">
              {me.email}
              <small>{ROLE_LABEL[me.role]}</small>
            </span>
          )}
          <Link to="/" className="cms-side__link">
            Xem trang
          </Link>
          <button type="button" className="cms-side__link" onClick={() => void logout()}>
            Đăng xuất
          </button>
        </div>
      </aside>
      <div className="cms-scrim" aria-hidden="true" onClick={closeNav} />

      <main id="cms-main" tabIndex={-1} className="cms__main">
      <header className="cms-top">
        <button
          type="button"
          ref={menuRef}
          className="cms-top__menu"
          aria-label="Mở menu quản trị"
          aria-expanded={navOpen}
          onClick={() => setNavOpen(true)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <h1 className="cms__title">{pageTitle}</h1>
        {view === 'content' && (
          <button type="button" className="cms-pill cms-pill--new" onClick={() => setCreating(true)}>
            {ADD_LABEL[type]}
          </button>
        )}
      </header>
      {source.status === 'success' &&
        source.data.body.source === 'google_drive' && (
          <p className="cms__source-note">
            Website đang hiển thị nội dung từ Google Drive. Hãy cập nhật file và
            mô tả trong thư mục Drive. Mục Nội dung và thống kê nội dung ở đây
            dành cho kho CMS riêng; tài khoản và tương tác vẫn được quản lý qua
            website.
          </p>
        )}

      {view === 'dashboard' && isAdmin ? (
        <Dashboard />
      ) : view === 'moderation' && isAdmin ? (
        <Moderation />
      ) : view === 'users' && isAdmin ? (
        <UsersPanel meId={me?.id ?? null} />
      ) : view === 'albums' ? (
        <AlbumsPanel />
      ) : (
        <CmsContent
          type={type}
          status={status}
          setStatus={setStatus}
          items={items}
          total={total}
          loading={loading}
          act={act}
          onEdit={setEditing}
          role={me?.role ?? 'member'}
          page={pageNumber}
          pages={pages}
          onPage={setPageNumber}
        />
      )}
      </main>

      {(creating || editing) && (
        <Editor
          initial={editing}
          defaultType={type}
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
  role: UserRole
  page: number
  pages: number
  onPage: (page: number) => void
  type: ContentType
  status: ContentStatus | null
  setStatus: (s: ContentStatus | null) => void
  items: ContentAdmin[]
  total: number
  loading: boolean
  act: (fn: () => Promise<unknown>, opts?: ActOpts) => Promise<void>
  onEdit: (c: ContentAdmin) => void
}

/** View quản lý nội dung (tách khỏi Cms để đọc dễ hơn). */
function CmsContent({
  role,
  page,
  pages,
  onPage,
  type,
  status,
  setStatus,
  items,
  total,
  loading,
  act,
  onEdit,
}: CmsContentProps) {
  const canPublish = role === 'admin' || role === 'editor'
  // Nội dung đang chờ xác nhận xoá (mở ConfirmDialog thay window.confirm)
  const [pendingDelete, setPendingDelete] = useState<ContentAdmin | null>(null)
  const isMusic = type === 'music'
  const [albumNames, setAlbumNames] = useState<Map<number, string>>(new Map())
  useEffect(() => {
    if (!isMusic) return
    let alive = true
    adminApi
      .albums()
      .then((list) => alive && setAlbumNames(new Map(list.map((a) => [a.id, a.title]))))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [isMusic])
  return (
    <>
      <div className="cms-toolbar">
        <div className="cms-seg" role="group" aria-label="Lọc theo trạng thái">
          {[{ value: null, label: 'Mọi trạng thái' }, ...STATUSES].map((st) => (
            <button
              key={st.value ?? 'all'}
              type="button"
              className={status === st.value ? 'cms-seg__btn cms-seg__btn--on' : 'cms-seg__btn'}
              onClick={() => setStatus(st.value)}
              aria-pressed={status === st.value}
            >
              {st.label}
            </button>
          ))}
        </div>
        {!loading && <span className="cms__count">{total} nội dung</span>}
      </div>

      <div className="cms-card">
        {loading ? (
          <p className="cms__status">Đang tải…</p>
        ) : items.length === 0 ? (
          <p className="cms__status">Chưa có nội dung nào.</p>
        ) : (
          <table className="cms-table">
            <thead>
              <tr>
                <th>Tiêu đề</th>
                {isMusic && <th>Album</th>}
                <th>Trạng thái</th>
                <th>Cập nhật</th>
                <th className="cms-table__actions">
                  <span className="sr-only">Thao tác</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => {
                const locked = !canPublish && c.status === 'published'
                const more = [
                  ...(canPublish
                    ? [
                        c.status !== 'published'
                          ? {
                              label: 'Đăng',
                              onClick: () =>
                                void act(() => adminApi.publish(c.id), { success: `Đã đăng “${c.title}”` }),
                            }
                          : {
                              label: 'Gỡ về nháp',
                              onClick: () =>
                                void act(() => adminApi.unpublish(c.id), {
                                  success: `Đã gỡ “${c.title}” về nháp`,
                                  undo: () => adminApi.publish(c.id),
                                }),
                            },
                      ]
                    : []),
                  ...(canPublish && c.status !== 'archived'
                    ? [
                        {
                          label: 'Lưu trữ',
                          onClick: () =>
                            void act(() => adminApi.archive(c.id), {
                              success: `Đã lưu trữ “${c.title}”`,
                              undo: () =>
                                c.status === 'published' ? adminApi.publish(c.id) : adminApi.unpublish(c.id),
                            }),
                        },
                      ]
                    : []),
                  {
                    label: 'Nhân bản',
                    onClick: () =>
                      void act(() => adminApi.duplicate(c.id), { success: `Đã nhân bản “${c.title}”` }),
                  },
                  ...(canPublish ? [{ label: 'Xoá', danger: true, onClick: () => setPendingDelete(c) }] : []),
                ]
                return (
                  <tr key={c.id}>
                    <td className="cms-table__main">
                      <span className="cms-table__title">{c.title}</span>
                      <span className="cms-table__sub">
                        /{c.slug}
                        {c.author_email && ` · ${c.author_email}`}
                      </span>
                    </td>
                    {isMusic && (
                      <td className="cms-table__type">
                        {c.album_id ? (
                          <>
                            {albumNames.get(c.album_id) ?? 'Album'}
                            {c.track_no && ` · #${c.track_no}`}
                          </>
                        ) : (
                          'Bài lẻ'
                        )}
                      </td>
                    )}
                    <td className="cms-table__status">
                      <span className={`cms-badge cms-badge--${c.status}`}>{STATUS_LABEL[c.status]}</span>
                    </td>
                    <td className="cms-table__time">{fmtTime(c.updated_at)}</td>
                    <td className="cms-table__actions">
                      <div className="cms-table__btns">
                      <button
                        type="button"
                        className="cms-pill"
                        disabled={locked}
                        title={locked ? 'Nhân bản bài đã đăng để đề xuất chỉnh sửa' : undefined}
                        onClick={() => onEdit(c)}
                      >
                        Sửa
                      </button>
                      <RowMenu label={`Thao tác khác cho “${c.title}”`} items={more} />
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <CmsPagination
        page={page}
        pages={pages}
        onChange={onPage}
        label="Phân trang nội dung"
      />

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

function RowMenu({ label, items }: {
  label: string
  items: { label: string; danger?: boolean; onClick: () => void }[]
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const initialFocus = useRef<'first' | 'last'>('first')
  const menuId = useId()
  const close = () => { setOpen(false); trigger.current?.focus() }
  useEffect(() => {
    if (!open) return
    const controls = ref.current?.querySelectorAll<HTMLElement>('[role="menuitem"]')
    controls?.[initialFocus.current === 'last' ? controls.length - 1 : 0]?.focus()
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('mousedown', onDown)
    }
  }, [open])
  return (
    <div className="cms-menu" ref={ref}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false) }}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && open) { e.preventDefault(); e.stopPropagation(); close() }
      }}>
      <button
        type="button"
        ref={trigger}
        className="cms-pill cms-pill--icon"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => { initialFocus.current = 'first'; setOpen((v) => !v) }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault()
            initialFocus.current = e.key === 'ArrowUp' ? 'last' : 'first'
            setOpen(true)
          }
        }}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="5" cy="12" r="1.8" fill="currentColor" />
          <circle cx="12" cy="12" r="1.8" fill="currentColor" />
          <circle cx="19" cy="12" r="1.8" fill="currentColor" />
        </svg>
      </button>
      {open && (
        <div className="cms-menu__list" role="menu" id={menuId} aria-label={label}
          onKeyDown={(e) => {
            if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return
            e.preventDefault()
            const controls = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('[role="menuitem"]'))
            const index = controls.indexOf(document.activeElement as HTMLElement)
            const next = e.key === 'Home' ? 0 : e.key === 'End' ? controls.length - 1
              : (index + (e.key === 'ArrowDown' ? 1 : -1) + controls.length) % controls.length
            controls[next]?.focus()
          }}>
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              tabIndex={-1}
              className={item.danger ? 'cms-menu__item cms-menu__item--danger' : 'cms-menu__item'}
              onClick={() => {
                close()
                item.onClick()
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function CmsPagination({
  page,
  pages,
  onChange,
  label,
}: {
  page: number
  pages: number
  onChange: (page: number) => void
  label: string
}) {
  if (pages <= 1) return null
  return (
    <nav className="cms-pagination" aria-label={label}>
      <button
        type="button"
        className="cms-pill"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Trang trước
      </button>
      <span aria-live="polite">
        Trang {page}/{pages}
      </span>
      <button
        type="button"
        className="cms-pill"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Trang sau
      </button>
    </nav>
  )
}
