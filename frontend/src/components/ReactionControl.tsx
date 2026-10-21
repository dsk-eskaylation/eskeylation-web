import { useEffect, useId, useRef, useState, type PointerEvent } from 'react'
import type { ReactionKind } from '../api/community'
import {
  ReactionIcon,
  REACTION_COLOR,
  REACTION_LABEL,
  REACTION_ORDER,
  ThumbIcon,
} from './reactionIcons'

/** Nút cảm xúc + bảng chọn 6 loại. Dùng cho cả bài viết lẫn bình luận.

    Sửa lỗi "không bấm được cảm xúc": mở khi hover (desktop) và GIỮ mở bằng
    grace-delay khi rê chuột qua khoảng trống giữa nút và bảng; trên di động thì
    NHẤN GIỮ để mở. Bấm nút chính = bật/tắt "Thích". */
export function ReactionControl({
  mine,
  disabled,
  variant,
  onToggle,
  onPick,
}: {
  mine: ReactionKind | null
  disabled?: boolean
  variant: 'post' | 'comment'
  onToggle: () => void
  onPick: (kind: ReactionKind) => void
}) {
  const [open, setOpen] = useState(false)
  const closeTimer = useRef<number | null>(null)
  const pressTimer = useRef<number | null>(null)
  const openedByHold = useRef(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const focusPicker = useRef(false)
  const pickerId = useId()
  useEffect(() => {
    if (open && focusPicker.current) {
      rootRef.current?.querySelector<HTMLButtonElement>('.cpost__picker-item')?.focus()
      focusPicker.current = false
    }
  }, [open])

  const clearClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }
  const scheduleClose = () => {
    clearClose()
    closeTimer.current = window.setTimeout(() => {
      if (!rootRef.current?.contains(document.activeElement)) setOpen(false)
    }, 280)
  }
  const openNow = () => {
    clearClose()
    if (!disabled) setOpen(true)
  }
  const clearPress = () => {
    if (pressTimer.current) {
      clearTimeout(pressTimer.current)
      pressTimer.current = null
    }
  }

  useEffect(() => () => {
    clearClose()
    clearPress()
  }, [])

  // Di động: nhấn giữ ~320ms để mở bảng cảm xúc
  const onPointerDown = (e: PointerEvent) => {
    if (e.pointerType !== 'touch' || disabled) return
    openedByHold.current = false
    pressTimer.current = window.setTimeout(() => {
      openedByHold.current = true
      setOpen(true)
    }, 320)
  }

  const handleMainClick = () => {
    if (openedByHold.current) {
      // Vừa mở bảng bằng nhấn giữ -> lần click này không toggle
      openedByHold.current = false
      return
    }
    if (!disabled) onToggle()
  }

  const isPost = variant === 'post'
  function openWithKeyboard() {
    clearClose()
    focusPicker.current = true
    if (open) {
      rootRef.current?.querySelector<HTMLButtonElement>('.cpost__picker-item')?.focus()
      focusPicker.current = false
    } else setOpen(true)
  }
  const mainClass = isPost
    ? mine
      ? 'cpost__act cpost__act--on'
      : 'cpost__act'
    : mine
      ? 'ccmt__react ccmt__react--on'
      : 'ccmt__react'

  return (
    <div
      ref={rootRef}
      className={isPost ? 'cpost__react-wrap' : 'ccmt__react-wrap'}
      onMouseLeave={scheduleClose}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) { clearClose(); setOpen(false) }
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.preventDefault()
          event.stopPropagation()
          setOpen(false)
          triggerRef.current?.focus()
        }
      }}
    >
      <button
        type="button"
        className={mainClass}
        onMouseEnter={openNow}
        disabled={disabled}
        onClick={handleMainClick}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') { event.preventDefault(); openWithKeyboard() }
        }}
        onPointerDown={onPointerDown}
        onPointerUp={clearPress}
        onPointerLeave={clearPress}
        style={mine ? { color: REACTION_COLOR[mine] } : undefined}
      >
        {isPost && (
          <span className="cpost__act-icon">
            {mine ? <ReactionIcon kind={mine} /> : <ThumbIcon />}
          </span>
        )}
        {mine ? REACTION_LABEL[mine] : 'Thích'}
      </button>
      <button ref={triggerRef} type="button" className="reaction-picker-trigger" disabled={disabled}
        aria-label="Chọn cảm xúc" aria-expanded={open} aria-controls={open ? pickerId : undefined}
        onClick={() => open ? setOpen(false) : openWithKeyboard()}
        onKeyDown={(event) => { if (event.key === 'ArrowDown') { event.preventDefault(); openWithKeyboard() } }}>
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      </button>
      {open && (
        <div
          id={pickerId}
          role="group"
          aria-label="Chọn cảm xúc"
          className={isPost ? 'cpost__picker' : 'cpost__picker cpost__picker--compact'}
          onMouseEnter={clearClose}
          onMouseLeave={scheduleClose}
          onKeyDown={(event) => {
            const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button')]
            const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
              : ['ArrowRight', 'ArrowDown'].includes(event.key) ? (index + 1) % buttons.length
              : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? (index - 1 + buttons.length) % buttons.length : null
            if (next !== null) { event.preventDefault(); buttons[next]?.focus() }
          }}
        >
          {REACTION_ORDER.map((k) => (
            <button
              key={k}
              type="button"
              className="cpost__picker-item"
              title={REACTION_LABEL[k]}
              aria-label={REACTION_LABEL[k]}
              style={{ color: REACTION_COLOR[k] }}
              onClick={() => {
                setOpen(false)
                openedByHold.current = false
                triggerRef.current?.focus()
                onPick(k)
              }}
            >
              <ReactionIcon kind={k} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
