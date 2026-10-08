import emptyImg from '../assets/figma/empty-state.png'
import './EmptyState.css'

interface Props {
  title: string
  hint?: string
}

/** Trạng thái rỗng dùng chung (Figma component 1:43 "Frame 167"):
    ảnh 200x200 + dòng chữ 30 Light. */
export function EmptyState({ title, hint }: Props) {
  return (
    <div className="empty-state">
      <img className="empty-state__img" src={emptyImg} alt="" aria-hidden="true" />
      <p className="empty-state__title">{title}</p>
      {hint && <p className="empty-state__hint">{hint}</p>}
    </div>
  )
}
