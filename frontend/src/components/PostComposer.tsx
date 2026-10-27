import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { community } from '../api/community'
import { Modal } from './Modal'
import { useToast } from './Toast'
import './PostComposer.css'

const MAX_IMAGES = 10
const MAX_CHARS = 5000
const ACCEPT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

interface Picked {
  key: string
  preview: string
  name: string
  status: 'uploading' | 'done' | 'error'
  mediaId?: number
  error?: string
}

/** Ô "Bạn đang nghĩ gì?" mở hộp thoại tạo bài: chữ + tối đa 10 ảnh, chờ admin duyệt. */
export function PostComposer({ name }: { name: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="composer-bar">
        <span className="composer-bar__avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
        <button type="button" className="composer-bar__prompt" onClick={() => setOpen(true)}>
          Bạn đang nghĩ gì về ESKAYLATION?
        </button>
        <button type="button" className="composer-bar__photo" onClick={() => setOpen(true)} aria-label="Đăng ảnh">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="3" />
            <circle cx="9" cy="10" r="1.6" />
            <path d="m4 17 5-5 4 4 2.5-2.5L20 17" />
          </svg>
        </button>
      </div>
      {open && <ComposerDialog name={name} onClose={() => setOpen(false)} />}
    </>
  )
}

function ComposerDialog({ name, onClose }: { name: string; onClose: () => void }) {
  const { notify } = useToast()
  const [text, setText] = useState('')
  const [images, setImages] = useState<Picked[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const previews = useRef(new Set<string>())
  const textRef = useRef<HTMLTextAreaElement>(null)

  // Modal tự focus nút đầu tiên; đưa con trỏ vào ô nội dung để gõ ngay.
  useEffect(() => textRef.current?.focus(), [])

  useEffect(() => {
    const urls = previews.current
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [])

  const uploading = images.some((image) => image.status === 'uploading')
  const ready = text.trim().length > 0 && !uploading && !sending

  function addFiles(files: FileList | File[]) {
    setError(null)
    const list = Array.from(files)
    const room = MAX_IMAGES - images.length
    if (list.length > room) setError(`Mỗi bài tối đa ${MAX_IMAGES} ảnh.`)
    for (const file of list.slice(0, Math.max(room, 0))) {
      if (!ACCEPT.includes(file.type)) {
        setError('Chỉ hỗ trợ ảnh JPG, PNG, WebP hoặc GIF.')
        continue
      }
      const key = `${file.name}-${file.size}-${Math.random()}`
      const preview = URL.createObjectURL(file)
      previews.current.add(preview)
      setImages((list) => [...list, { key, preview, name: file.name, status: 'uploading' }])
      community.uploadImage(file).then(
        (media) => setImages((list) => list.map((i) => (i.key === key ? { ...i, status: 'done', mediaId: media.id } : i))),
        (err: unknown) => setImages((list) => list.map((i) => (i.key === key
          ? { ...i, status: 'error', error: err instanceof Error ? err.message : 'Tải ảnh thất bại' } : i))),
      )
    }
  }

  function remove(key: string) {
    setImages((list) => list.filter((image) => image.key !== key))
  }

  function close() {
    if ((text.trim() || images.length) && !window.confirm('Bỏ bài viết đang soạn?')) return
    onClose()
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready) return
    setSending(true)
    setError(null)
    try {
      const ids = images.filter((i) => i.status === 'done' && i.mediaId).map((i) => i.mediaId as number)
      const res = await community.submitPost(text.trim(), ids)
      notify(res.message, { tone: 'success' })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chưa gửi được bài.')
    } finally {
      setSending(false)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  return (
    <Modal onClose={close} label="Tạo bài viết" showClose={false}>
      <form
        className={dragging ? 'composer composer--drag' : 'composer'}
        onSubmit={submit}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false) }}
        onDrop={onDrop}
      >
        <header className="composer__head">
          <button type="button" className="composer__link" onClick={close}>Huỷ</button>
          <h2>Tạo bài viết</h2>
          <button type="submit" className="composer__post" disabled={!ready}>
            {sending ? 'Đang gửi…' : 'Đăng'}
          </button>
        </header>

        <div className="composer__author">
          <span className="composer-bar__avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
          <span>{name}</span>
        </div>

        <label className="sr-only" htmlFor="composer-text">Nội dung bài viết</label>
        <textarea
          ref={textRef}
          id="composer-text"
          className="composer__text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={MAX_CHARS}
          rows={images.length ? 3 : 6}
          placeholder="Chia sẻ kỷ niệm, cảm nhận về DSK…"
        />

        {images.length > 0 && (
          <ul className={`composer__images composer__images--n${Math.min(images.length, 3)}`}>
            {images.map((image) => (
              <li key={image.key} className={`composer__image composer__image--${image.status}`}>
                <img src={image.preview} alt={image.name} />
                {image.status === 'uploading' && <span className="composer__state" role="status">Đang tải…</span>}
                {image.status === 'error' && <span className="composer__state" role="alert">{image.error}</span>}
                <button type="button" className="composer__remove" onClick={() => remove(image.key)} aria-label={`Gỡ ảnh ${image.name}`}>×</button>
              </li>
            ))}
          </ul>
        )}

        <div className="composer__tools">
          <button
            type="button"
            className="composer__add"
            onClick={() => fileRef.current?.click()}
            disabled={images.length >= MAX_IMAGES}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="5" width="18" height="14" rx="3" />
              <circle cx="9" cy="10" r="1.6" />
              <path d="m4 17 5-5 4 4 2.5-2.5L20 17" />
            </svg>
            Thêm ảnh {images.length > 0 && `(${images.length}/${MAX_IMAGES})`}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT.join(',')}
            multiple
            hidden
            onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }}
          />
          <span className="composer__count" aria-live="polite">{text.length}/{MAX_CHARS}</span>
        </div>

        {error && <p className="composer__error" role="alert">{error}</p>}
        <p className="composer__hint">Bài viết sẽ hiển thị sau khi được admin duyệt. Kéo thả ảnh vào đây để thêm nhanh.</p>
      </form>
    </Modal>
  )
}
