import { useEffect, useRef } from 'react'

/** Gọi onNear khi đã cuộn qua `at` (mặc định 70%) chiều cao trang, để nạp trước
    phần bên dưới trước khi người xem tới đáy. `count` đổi (vừa thêm mục) thì kiểm
    tra lại ngay — trang còn ngắn hơn màn hình vẫn nạp tiếp được. */
export function useScrollPreload(onNear: () => void, enabled: boolean, count: number, at = 0.7) {
  const callback = useRef(onNear)
  useEffect(() => {
    callback.current = onNear
  })

  useEffect(() => {
    if (!enabled) return
    let frame = 0
    const check = () => {
      frame = 0
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight * at) {
        callback.current()
      }
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(check)
    }
    schedule()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      if (frame) cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [enabled, count, at])
}
