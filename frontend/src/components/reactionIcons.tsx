import type { ReactNode } from 'react'
import type { ReactionKind } from '../api/community'

/* Bộ icon line tối giản (24x24, dùng currentColor) — thay emoji cho gọn gàng,
   chuyên nghiệp. Mỗi reaction có màu nhấn riêng khi được chọn/hiển thị. */

export const REACTION_COLOR: Record<ReactionKind, string> = {
  like: '#4a90e2',
  love: '#e0245e',
  haha: '#f6b93b',
  wow: '#f6b93b',
  sad: '#f6b93b',
  angry: '#e2593b',
}

export const REACTION_LABEL: Record<ReactionKind, string> = {
  like: 'Thích',
  love: 'Yêu thích',
  haha: 'Haha',
  wow: 'Wow',
  sad: 'Buồn',
  angry: 'Phẫn nộ',
}

export const REACTION_ORDER: ReactionKind[] = [
  'like',
  'love',
  'haha',
  'wow',
  'sad',
  'angry',
]

const S = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

function Face({ children }: { children: ReactNode }) {
  return (
    <>
      <circle cx="12" cy="12" r="9" {...S} />
      {children}
    </>
  )
}

export function ReactionIcon({ kind }: { kind: ReactionKind }) {
  const inner = () => {
    switch (kind) {
      case 'like':
        return (
          <path
            d="M7 21V10l4.5-6.5a1.6 1.6 0 0 1 2.7 1.5L13 9h5.2a2 2 0 0 1 2 2.4l-1.4 7A2 2 0 0 1 16.9 20H7zM7 10H4v11h3"
            {...S}
          />
        )
      case 'love':
        return (
          <path
            d="M12 20s-7-4.4-7-9.3A3.7 3.7 0 0 1 12 8a3.7 3.7 0 0 1 7 2.7C19 15.6 12 20 12 20z"
            {...S}
          />
        )
      case 'haha':
        return (
          <Face>
            <path d="M8.5 9.5h.01M15.5 9.5h.01" {...S} />
            <path d="M7.5 13.5a4.5 4.5 0 0 0 9 0z" {...S} />
          </Face>
        )
      case 'wow':
        return (
          <Face>
            <circle cx="8.5" cy="9.5" r="0.6" fill="currentColor" />
            <circle cx="15.5" cy="9.5" r="0.6" fill="currentColor" />
            <ellipse cx="12" cy="15" rx="2" ry="2.6" {...S} />
          </Face>
        )
      case 'sad':
        return (
          <Face>
            <path d="M8.5 9.5h.01M15.5 9.5h.01" {...S} />
            <path d="M8.5 16a4 4 0 0 1 7 0" {...S} />
          </Face>
        )
      case 'angry':
        return (
          <Face>
            <path d="M7.5 8.5l2 1M16.5 8.5l-2 1" {...S} />
            <path d="M8.5 15.5a4 4 0 0 1 7 0" {...S} />
          </Face>
        )
    }
  }
  return (
    <svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">
      {inner()}
    </svg>
  )
}

export function ThumbIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M7 21V10l4.5-6.5a1.6 1.6 0 0 1 2.7 1.5L13 9h5.2a2 2 0 0 1 2 2.4l-1.4 7A2 2 0 0 1 16.9 20H7zM7 10H4v11h3"
        {...S}
      />
    </svg>
  )
}

export function CommentIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20 15a3 3 0 0 1-3 3H8l-4 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3z"
        {...S}
      />
    </svg>
  )
}

export function BookmarkIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M6 4h12a1 1 0 0 1 1 1v16l-7-4.2L5 21V5a1 1 0 0 1 1-1z"
        {...S}
        fill={filled ? 'currentColor' : 'none'}
      />
    </svg>
  )
}
