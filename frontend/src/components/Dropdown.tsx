import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import './Dropdown.css'

export interface DropdownOption {
  value: string
  label: string
  meta?: string
  image?: string | null
}

interface Props {
  label: string
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
}

/** Listbox that opens below its trigger; native <select> popups cover the control on macOS. */
export function Dropdown({ label, value, options, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const id = useId()
  const selected = options.find((o) => o.value === value) ?? options[0]

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  useEffect(() => {
    if (open) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [open, active])

  const show = () => {
    setActive(Math.max(0, options.findIndex((o) => o.value === value)))
    setOpen(true)
  }
  const choose = (index: number) => {
    onChange(options[index].value)
    setOpen(false)
  }
  const onKey = (e: KeyboardEvent) => {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        show()
      }
      return
    }
    if (e.key === 'Escape' || e.key === 'Tab') {
      if (e.key === 'Escape') e.preventDefault()
      setOpen(false)
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(options.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(0, i - 1))
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault()
      setActive(e.key === 'Home' ? 0 : options.length - 1)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      choose(active)
    }
  }

  return (
    <div className="dropdown" ref={rootRef}>
      <button
        type="button"
        className={open ? 'dropdown__trigger dropdown__trigger--open' : 'dropdown__trigger'}
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={id}
        aria-activedescendant={open ? `${id}-${active}` : undefined}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKey}
      >
        <span className="dropdown__value">{selected?.label}</span>
        <svg className="dropdown__chevron" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <ul className="dropdown__list" id={id} role="listbox" aria-label={label} ref={listRef}>
          {options.map((option, index) => (
            <li
              key={option.value}
              id={`${id}-${index}`}
              role="option"
              aria-selected={option.value === value}
              className={[
                'dropdown__option',
                index === active && 'dropdown__option--active',
                option.value === value && 'dropdown__option--selected',
              ]
                .filter(Boolean)
                .join(' ')}
              onMouseEnter={() => setActive(index)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(index)}
            >
              {option.image !== undefined &&
                (option.image ? (
                  <img className="dropdown__thumb" src={option.image} alt="" loading="lazy" />
                ) : (
                  <span className="dropdown__thumb dropdown__thumb--empty" aria-hidden="true" />
                ))}
              <span className="dropdown__label">{option.label}</span>
              {option.meta && <span className="dropdown__meta">{option.meta}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
