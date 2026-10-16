import { useEffect, useRef, useState, type PointerEvent } from 'react'
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

  const clearClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }
  const scheduleClose = () => {
    clearClose()
    closeTimer.current = window.setTimeout(() => setOpen(false), 280)
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
  const mainClass = isPost
    ? mine
      ? 'cpost__act cpost__act--on'
      : 'cpost__act'
    : mine
      ? 'ccmt__react ccmt__react--on'
      : 'ccmt__react'

  return (
    <div
      className={isPost ? 'cpost__react-wrap' : 'ccmt__react-wrap'}
      onMouseEnter={openNow}
      onMouseLeave={scheduleClose}
    >
      <button
        type="button"
        className={mainClass}
        disabled={disabled}
        onClick={handleMainClick}
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
      {open && (
        <div
          className={isPost ? 'cpost__picker' : 'cpost__picker cpost__picker--compact'}
          onMouseEnter={clearClose}
          onMouseLeave={scheduleClose}
        >
          {REACTION_ORDER.map((k) => (
            <button
              key={k}
              type="button"
              className="cpost__picker-item"
              title={REACTION_LABEL[k]}
              style={{ color: REACTION_COLOR[k] }}
              onClick={() => {
                setOpen(false)
                openedByHold.current = false
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
