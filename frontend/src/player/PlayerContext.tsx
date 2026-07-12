import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { ContentOut } from '../api/types'

export type RepeatMode = 'off' | 'all' | 'one'

/** URL audio để stream (theo thiết kế: body.audio_url). Null -> không phát được. */
export function audioUrl(c: ContentOut): string | null {
  const v = c.body.audio_url
  return typeof v === 'string' && v ? v : null
}

export function coverUrl(c: ContentOut): string | null {
  const primary = c.media.find((m) => m.is_primary) ?? c.media[0]
  return primary?.url ?? null
}

export function artistOf(c: ContentOut): string {
  return typeof c.body.artist === 'string' ? c.body.artist : 'DSK'
}

interface PlayerState {
  queue: ContentOut[]
  index: number
  current: ContentOut | null
  isPlaying: boolean
  repeat: RepeatMode
  shuffle: boolean
  currentTime: number
  duration: number
  /** Phát một danh sách từ vị trí start (mặc định 0). */
  playQueue: (items: ContentOut[], startIndex?: number) => void
  toggle: () => void
  next: () => void
  prev: () => void
  seek: (time: number) => void
  toggleShuffle: () => void
  cycleRepeat: () => void
  stop: () => void
  /** Nhảy tới một vị trí trong hàng chờ. */
  jumpTo: (i: number) => void
  /** Bỏ một bài khỏi hàng chờ. */
  removeFromQueue: (i: number) => void
  /** Mở hộp thoại chọn thiết bị phát từ xa (Remote Playback API). */
  promptRemote: () => void
  /** Thiết bị phát từ xa có khả dụng không (Cast/AirPlay...). */
  remoteAvailable: boolean
}

const PlayerCtx = createContext<PlayerState | null>(null)

export function usePlayer(): PlayerState {
  const ctx = useContext(PlayerCtx)
  if (!ctx) throw new Error('usePlayer phải nằm trong <PlayerProvider>')
  return ctx
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [queue, setQueue] = useState<ContentOut[]>([])
  const [index, setIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [repeat, setRepeat] = useState<RepeatMode>('off')
  const [shuffle, setShuffle] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [remoteAvailable, setRemoteAvailable] = useState(false)
  // Lịch sử index để nút "trước" hoạt động đúng cả khi bật shuffle
  const historyRef = useRef<number[]>([])

  const current = queue[index] ?? null
  const currentId = current?.id ?? null

  const pickNextIndex = useCallback((): number | null => {
    if (queue.length === 0) return null
    if (shuffle) {
      if (queue.length === 1) return repeat === 'off' ? null : 0
      let n = index
      while (n === index) n = Math.floor(Math.random() * queue.length)
      return n
    }
    if (index < queue.length - 1) return index + 1
    return repeat === 'all' ? 0 : null
  }, [queue.length, shuffle, index, repeat])

  const playQueue = useCallback((items: ContentOut[], startIndex = 0) => {
    const playable = items.filter((it) => audioUrl(it))
    if (playable.length === 0) return
    // Map startIndex (theo items gốc) sang vị trí trong danh sách playable
    const startId = items[startIndex]?.id
    const mapped = Math.max(0, playable.findIndex((it) => it.id === startId))
    historyRef.current = []
    setQueue(playable)
    setIndex(mapped)
    setIsPlaying(true)
  }, [])

  const toggle = useCallback(() => {
    if (!current) return
    setIsPlaying((p) => !p)
  }, [current])

  const next = useCallback(() => {
    const n = pickNextIndex()
    if (n === null) {
      setIsPlaying(false)
      return
    }
    historyRef.current.push(index)
    setIndex(n)
    setIsPlaying(true)
  }, [pickNextIndex, index])

  const prev = useCallback(() => {
    const audio = audioRef.current
    // Lùi <3s: về đầu bài; ngược lại chuyển bài trước
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0
      return
    }
    if (shuffle && historyRef.current.length > 0) {
      const prevIdx = historyRef.current.pop() as number
      setIndex(prevIdx)
      setIsPlaying(true)
      return
    }
    setIndex((i) => (i > 0 ? i - 1 : repeat === 'all' ? queue.length - 1 : 0))
    setIsPlaying(true)
  }, [shuffle, repeat, queue.length])

  const seek = useCallback((time: number) => {
    const audio = audioRef.current
    if (audio) audio.currentTime = time
    setCurrentTime(time)
  }, [])

  const jumpTo = useCallback(
    (i: number) => {
      if (i < 0 || i >= queue.length) return
      historyRef.current.push(index)
      setIndex(i)
      setIsPlaying(true)
    },
    [queue.length, index],
  )

  const removeFromQueue = useCallback((i: number) => {
    setQueue((prev) => prev.filter((_, idx) => idx !== i))
    // Giữ bài đang phát: bỏ bài phía trước -> lùi index; bỏ chính nó -> bài kế
    // trượt vào vị trí này (index giữ nguyên, clamp ở render qua current).
    setIndex((prev) => (i < prev ? prev - 1 : prev))
  }, [])

  const promptRemote = useCallback(() => {
    const remote = audioRef.current?.remote
    if (remote?.prompt) void remote.prompt().catch(() => {})
  }, [])

  const toggleShuffle = useCallback(() => setShuffle((s) => !s), [])
  const cycleRepeat = useCallback(
    () => setRepeat((r) => (r === 'off' ? 'all' : r === 'all' ? 'one' : 'off')),
    [],
  )
  const stop = useCallback(() => {
    setIsPlaying(false)
    setQueue([])
    setIndex(0)
  }, [])

  // Đổi bài -> nạp src mới. Chỉ chạy khi id bài đổi (không phải khi play/pause).
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !current) return
    const url = audioUrl(current)
    if (!url) return
    audio.src = url
    audio.load()
    setCurrentTime(0)
    setDuration(0)
    if (isPlaying) void audio.play().catch(() => setIsPlaying(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId])

  // Play/pause đồng bộ với state
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !current) return
    if (isPlaying) void audio.play().catch(() => setIsPlaying(false))
    else audio.pause()
  }, [isPlaying, current])

  // Xử lý khi hết bài: repeat one lặp lại, còn lại chuyển tiếp
  const handleEnded = useCallback(() => {
    if (repeat === 'one') {
      const audio = audioRef.current
      if (audio) {
        audio.currentTime = 0
        void audio.play().catch(() => setIsPlaying(false))
      }
      return
    }
    next()
  }, [repeat, next])

  // MediaSession: metadata + điều khiển từ màn hình khoá / tai nghe (mobile/iPad)
  useEffect(() => {
    if (!('mediaSession' in navigator) || !current) return
    const cover = coverUrl(current)
    navigator.mediaSession.metadata = new MediaMetadata({
      title: current.title,
      artist: artistOf(current),
      album: 'Eskaylation',
      artwork: cover
        ? [{ src: cover, sizes: '512x512', type: 'image/jpeg' }]
        : undefined,
    })
    navigator.mediaSession.setActionHandler('play', () => setIsPlaying(true))
    navigator.mediaSession.setActionHandler('pause', () => setIsPlaying(false))
    navigator.mediaSession.setActionHandler('previoustrack', prev)
    navigator.mediaSession.setActionHandler('nexttrack', next)
    navigator.mediaSession.setActionHandler('seekto', (e) => {
      if (typeof e.seekTime === 'number') seek(e.seekTime)
    })
  }, [current, prev, next, seek])

  useEffect(() => {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused'
    }
  }, [isPlaying])

  // Theo dõi thiết bị phát từ xa (Chromecast/AirPlay...) qua Remote Playback API
  useEffect(() => {
    const remote = audioRef.current?.remote
    if (!remote?.watchAvailability) return
    let watchId: number | null = null
    remote
      .watchAvailability((available) => setRemoteAvailable(available))
      .then((id) => {
        watchId = id
      })
      .catch(() => {})
    return () => {
      if (watchId !== null) void remote.cancelWatchAvailability(watchId).catch(() => {})
    }
  }, [])

  const value = useMemo<PlayerState>(
    () => ({
      queue,
      index,
      current,
      isPlaying,
      repeat,
      shuffle,
      currentTime,
      duration,
      playQueue,
      toggle,
      next,
      prev,
      seek,
      toggleShuffle,
      cycleRepeat,
      stop,
      jumpTo,
      removeFromQueue,
      promptRemote,
      remoteAvailable,
    }),
    [
      queue, index, current, isPlaying, repeat, shuffle, currentTime, duration,
      playQueue, toggle, next, prev, seek, toggleShuffle, cycleRepeat, stop,
      jumpTo, removeFromQueue, promptRemote, remoteAvailable,
    ],
  )

  return (
    <PlayerCtx.Provider value={value}>
      {children}
      {/* Audio bền bỉ ở gốc app -> phát nền, không dừng khi đổi trang */}
      <audio
        ref={audioRef}
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
        onEnded={handleEnded}
      />
    </PlayerCtx.Provider>
  )
}
