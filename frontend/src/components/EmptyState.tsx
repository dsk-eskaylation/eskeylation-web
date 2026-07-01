import './EmptyState.css'

interface Props {
  title: string
  hint?: string
}

/** Trạng thái rỗng dùng chung cho music/photo/community. */
export function EmptyState({ title, hint }: Props) {
  return (
    <div className="empty-state">
      <p className="empty-state__title">{title}</p>
      {hint && <p className="empty-state__hint">{hint}</p>}
    </div>
  )
}
