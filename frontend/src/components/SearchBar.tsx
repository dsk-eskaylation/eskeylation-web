import './SearchBar.css'

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: boolean
  onClear?: () => void
}

/** Ô tìm kiếm bo tròn dùng chung (Figma EL-e3f6ec2b): viền 0.5px, icon kính lúp,
    khi có chữ hiện nút X, khi lỗi đổi màu viền. */
export function SearchBar({
  value,
  onChange,
  placeholder = 'Tìm kiếm bài hát',
  error,
  onClear,
}: Props) {
  const cls = [
    'search-bar',
    value ? 'search-bar--typing' : '',
    error ? 'search-bar--error' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={cls}>
      <svg className="search-bar__icon" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <line
          x1="12.5"
          y1="12.5"
          x2="16"
          y2="16"
          stroke="currentColor"
          strokeWidth="1.5"
        />
      </svg>
      <input
        className="search-bar__input"
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && onClear && (
        <button
          type="button"
          className="search-bar__clear"
          onClick={onClear}
          aria-label="Xoá tìm kiếm"
        >
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <line x1="3" y1="3" x2="13" y2="13" stroke="currentColor" strokeWidth="1.5" />
            <line x1="13" y1="3" x2="3" y2="13" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
      )}
    </div>
  )
}
