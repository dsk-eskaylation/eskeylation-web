import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Shareable search/page state, including browser Back and Forward. */
export function useLibraryParams() {
  const [params, setParams] = useSearchParams()
  const requestedPage = Number(params.get('page') ?? 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const q = params.get('q') ?? ''
  const setPage = useCallback((value: number, replace = false) => {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (value <= 1) next.delete('page')
      else next.set('page', String(value))
      return next
    }, { replace })
  }, [setParams])
  function setQuery(value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (value) next.set('q', value)
      else next.delete('q')
      next.delete('page')
      return next
    }, { replace: true })
  }
  return { q, page, setPage, setQuery }
}
