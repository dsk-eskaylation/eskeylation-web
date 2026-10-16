import { useEffect, useState } from 'react'

type State<T> =
  | { status: 'loading' }
  | { status: 'error'; error: unknown }
  | { status: 'success'; data: T }

/** Gọi một hàm trả Promise và theo dõi trạng thái loading/error/success. */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): State<T> {
  const [state, setState] = useState<State<T>>({ status: 'loading' })

  // Deps do caller truyền vào, cố ý bỏ fetcher khỏi deps
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    let alive = true
    setState({ status: 'loading' })
    fetcher()
      .then((data) => alive && setState({ status: 'success', data }))
      .catch((error) => alive && setState({ status: 'error', error }))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}

/** Debounce giá trị search cho mượt (gõ xong 300ms mới gọi API). */
export function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
