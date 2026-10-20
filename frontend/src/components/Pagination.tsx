import './Pagination.css'

interface Props {
  page: number
  pages: number
  label: string
  onChange: (page: number) => void
  busy?: boolean
}

function pageList(page: number, pages: number): (number | null)[] {
  if (pages <= 5) return Array.from({ length: pages }, (_, i) => i + 1)
  if (page <= 2) return [1, 2, 3, null, pages]
  if (page >= pages - 1) return [1, null, pages - 2, pages - 1, pages]
  return [1, null, page, null, pages]
}

/** Compact enough for mobile; shared by the photo library and community feed. */
export function Pagination({ page, pages, label, onChange, busy = false }: Props) {
  if (pages <= 1) return null
  return (
    <nav className="pagination" aria-label={label} aria-busy={busy}>
      <ul className="pagination__list">
        <li>
          <button type="button" className="pagination__button" aria-label="Trang trước"
            disabled={busy || page <= 1} onClick={() => onChange(page - 1)}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m14 6-6 6 6 6" />
            </svg>
          </button>
        </li>
        {pageList(page, pages).map((number, index) => (
          <li key={number ?? `gap-${index}`}>
            {number === null ? (
              <span className="pagination__gap" aria-hidden="true">…</span>
            ) : (
              <button type="button" className="pagination__button"
                aria-label={`Trang ${number}`} aria-current={number === page ? 'page' : undefined}
                disabled={busy} onClick={() => number !== page && onChange(number)}>
                {number}
              </button>
            )}
          </li>
        ))}
        <li>
          <button type="button" className="pagination__button" aria-label="Trang sau"
            disabled={busy || page >= pages} onClick={() => onChange(page + 1)}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m10 6 6 6-6 6" />
            </svg>
          </button>
        </li>
      </ul>
      <p className="pagination__status" aria-live="polite" aria-atomic="true">
        {busy ? `Đang tải trang ${page}…` : `Trang ${page} / ${pages}`}
      </p>
    </nav>
  )
}
