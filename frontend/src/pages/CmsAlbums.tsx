import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { adminApi, type AlbumAdmin } from '../api/admin'
import type { AlbumKind } from '../api/types'
import { KIND_LABEL } from '../components/AlbumShelf'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { FormError } from '../components/FormError'
import { useToast } from '../components/Toast'

const EMPTY = { title: '', kind: 'album' as AlbumKind, year: '', cover_url: '', position: '0', description: '' }

export function AlbumsPanel() {
  const { notify } = useToast()
  const [albums, setAlbums] = useState<AlbumAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState<AlbumAdmin | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setAlbums(await adminApi.albums())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được danh sách album')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const field = (key: keyof typeof EMPTY) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  const edit = (album: AlbumAdmin) => {
    setEditingId(album.id)
    setError(null)
    setForm({
      title: album.title,
      kind: album.kind,
      year: album.year ? String(album.year) : '',
      cover_url: album.cover_url ?? '',
      position: String(album.position),
      description: album.description ?? '',
    })
  }

  const reset = () => {
    setEditingId(null)
    setForm(EMPTY)
    setError(null)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    const payload = {
      title: form.title.trim(),
      kind: form.kind,
      year: form.year ? Number(form.year) : null,
      cover_url: form.cover_url.trim() || null,
      position: Number(form.position) || 0,
      description: form.description.trim() || null,
    }
    try {
      if (editingId) await adminApi.updateAlbum(editingId, payload)
      else await adminApi.createAlbum(payload)
      notify(editingId ? `Đã lưu album “${payload.title}”` : `Đã tạo album “${payload.title}”`)
      reset()
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được album')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cms-mod">
      <section>
        <p className="cms__section-label">{editingId ? 'Sửa album' : 'Tạo album'}</p>
        <form className="cms-editor" onSubmit={submit}>
          <div className="cms-editor__row">
            <label className="cms-field">
              <span>Tên album</span>
              <input {...field('title')} required maxLength={255} />
            </label>
            <label className="cms-field">
              <span>Loại</span>
              <select {...field('kind')}>
                {(Object.keys(KIND_LABEL) as AlbumKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABEL[kind]}
                  </option>
                ))}
              </select>
            </label>
            <label className="cms-field">
              <span>Năm</span>
              <input {...field('year')} type="number" min={1990} max={2100} />
            </label>
            <label className="cms-field">
              <span>Thứ tự hiển thị</span>
              <input {...field('position')} type="number" min={0} max={10000} />
            </label>
          </div>
          <label className="cms-field">
            <span>Ảnh bìa (link HTTPS, tùy chọn)</span>
            <input {...field('cover_url')} placeholder="https://..." />
          </label>
          <label className="cms-field">
            <span>Mô tả (tùy chọn)</span>
            <textarea {...field('description')} rows={3} maxLength={5000} />
          </label>
          {error && <FormError id="cms-album-error" message={error} className="cms-error" />}
          <div className="cms-editor__row">
            <button type="submit" className="cms-pill cms-pill--new" disabled={busy}>
              {busy ? 'Đang lưu…' : editingId ? 'Lưu album' : '+ Tạo album'}
            </button>
            {editingId && (
              <button type="button" className="cms-pill" onClick={reset}>
                Huỷ
              </button>
            )}
          </div>
        </form>
      </section>

      <section>
        <p className="cms__section-label">Album ({albums.length})</p>
        <p className="cms-field__hint">
          Gán bài vào album trong form sửa bài nhạc. Xoá album không xoá bài; bài sẽ chuyển về “Bài lẻ”.
        </p>
        {loading ? (
          <p className="cms__status">Đang tải…</p>
        ) : albums.length === 0 ? (
          <p className="cms__status">Chưa có album nào.</p>
        ) : (
          <ul className="cms__list">
            {albums.map((album) => (
              <li key={album.id} className="cms__row">
                <div className="cms__row-main">
                  <div className="cms__row-text">
                    <span className="cms__row-title">{album.title}</span>
                    <span className="cms__row-meta">
                      {[KIND_LABEL[album.kind], album.year, `${album.track_count} bài`, `thứ tự ${album.position}`]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </div>
                </div>
                <div className="cms__row-actions">
                  <button type="button" className="cms-pill" onClick={() => edit(album)}>
                    Sửa
                  </button>
                  <button type="button" className="cms-pill" onClick={() => setDeleting(album)}>
                    Xoá
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {deleting && (
        <ConfirmDialog
          title="Xoá album?"
          message={`“${deleting.title}” sẽ bị xoá; ${deleting.track_count} bài trong album chuyển về “Bài lẻ”.`}
          onConfirm={async () => {
            await adminApi.deleteAlbum(deleting.id)
            notify(`Đã xoá album “${deleting.title}”`)
            if (editingId === deleting.id) reset()
            await load()
          }}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
