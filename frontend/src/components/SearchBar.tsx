import './SearchBar.css'

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}

/** Ô tìm kiếm bo tròn dùng chung (viền mờ, icon kính lúp). */
export function SearchBar({ value, onChange, placeholder = 'Tìm kiếm bài hát' }: Props) {
  return (
    <div className="search-bar">
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
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}
