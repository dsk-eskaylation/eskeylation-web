/** Only return iframe origins allowed by the API whitelist and CSP. */
export function toEmbedUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol)) return null
    const host = url.hostname.replace(/^www\./, '')
    const parts = url.pathname.replace(/^\/+|\/+$/g, '').split('/')
    let id: string | null = null
    if (host === 'youtu.be') id = parts[0]
    else if (host === 'youtube.com') {
      if (parts.length === 2 && ['embed', 'shorts'].includes(parts[0])) id = parts[1]
      else if (url.pathname === '/watch') id = url.searchParams.get('v')
    } else if (['vimeo.com', 'player.vimeo.com'].includes(host)) {
      if (/^(?:video\/)?\d+$/.test(parts.join('/'))) {
        return `https://player.vimeo.com/video/${parts.at(-1)}`
      }
    }
    return id && /^[A-Za-z0-9_-]{11}$/.test(id)
      ? `https://www.youtube.com/embed/${id}`
      : null
  } catch {
    return null
  }
}
