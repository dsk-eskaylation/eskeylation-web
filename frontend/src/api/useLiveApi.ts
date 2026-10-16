import { useSyncExternalStore } from 'react'
import { invalidatePublicCache } from './client'
import { useApi } from './useApi'

const listeners = new Set<() => void>()
let revision = ''
let timer: ReturnType<typeof setInterval> | null = null
let checking = false

async function checkCatalog() {
  if (checking || document.hidden || !navigator.onLine) return
  checking = true
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const response = await fetch('/api/catalog', {
      cache: 'no-store',
      credentials: 'omit',
      signal: controller.signal,
    })
    if (!response.ok) return
    const data: { revision: string | null } = await response.json()
    if (typeof data.revision !== 'string' || data.revision === revision) return
    revision = data.revision
    invalidatePublicCache()
    listeners.forEach((listener) => listener())
  } catch {
    // Preserve the current view during an outage; the next visible check retries.
  } finally {
    checking = false
    clearTimeout(timeout)
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    void checkCatalog()
    timer = setInterval(() => void checkCatalog(), 15000)
    window.addEventListener('focus', checkCatalog)
    window.addEventListener('online', checkCatalog)
    document.addEventListener('visibilitychange', checkCatalog)
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      if (timer !== null) clearInterval(timer)
      timer = null
      window.removeEventListener('focus', checkCatalog)
      window.removeEventListener('online', checkCatalog)
      document.removeEventListener('visibilitychange', checkCatalog)
    }
  }
}

const snapshot = () => revision
const idleSubscribe = () => () => {}

export function useCatalogRevision(enabled = true) {
  return useSyncExternalStore(enabled ? subscribe : idleSubscribe, snapshot)
}

/** Poll a tiny revision once per tab; reload lists only when Drive has changed. */
export function useLiveApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const current = useCatalogRevision()
  return useApi(fetcher, [current, ...deps], true)
}
