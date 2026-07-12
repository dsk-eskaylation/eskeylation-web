import { useState, type CSSProperties } from 'react'
import { usePlayer, artistOf, coverUrl } from '../player/PlayerContext'
import { submitLyrics } from '../api/music'
import type { ContentOut } from '../api/types'
import './PlayerBar.css'

type Panel = 'queue' | 'lyrics' | 'device' | null

function fmt(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function lyricsOf(c: ContentOut): string {
  return typeof c.body.lyrics === 'string' ? c.body.lyrics : ''
}

/** Hàng chờ: xem, nhảy tới, bỏ bài sắp phát. */
function QueuePanel() {
  const p = usePlayer()
  return (
    <div className="pbpanel">
      <h3 className="pbpanel__title">Hàng chờ</h3>
      <ol className="pbpanel__queue">
        {p.queue.map((t, i) => {
          const isCur = i === p.index
          return (
            <li
              key={`${t.id}-${i}`}
              className={isCur ? 'pbq pbq--cur' : 'pbq'}
            >
              <button
                type="button"
                className="pbq__main"
                onClick={() => p.jumpTo(i)}
                title={`Phát ${t.title}`}
              >
                {coverUrl(t) ? (
                  <img className="pbq__cover" src={coverUrl(t)!} alt="" />
                ) : (
                  <span className="pbq__cover pbq__cover--empty" />
                )}
                <span className="pbq__meta">
                  <span className="pbq__title">{t.title}</span>
                  <span className="pbq__artist">{artistOf(t)}</span>
                </span>
                {isCur && <span className="pbq__badge">Đang phát</span>}
              </button>
              {!isCur && (
                <button
                  type="button"
                  className="pbq__rm"
                  onClick={() => p.removeFromQueue(i)}
                  aria-label="Bỏ khỏi hàng chờ"
                  title="Bỏ khỏi hàng chờ"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" />
                    <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" />
                  </svg>
                </button>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/** Lời bài hát + đóng góp (chờ duyệt). */
function LyricsPanel() {
  const p = usePlayer()
  const [draft, setDraft] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [contrib, setContrib] = useState(false)
  const current = p.current
  if (!current) return null
  const lyrics = lyricsOf(current)

  async function send() {
    const body = draft.trim()
    if (!body || sending || !current) return
    setSending(true)
    setMsg(null)
    try {
      const res = await submitLyrics(current.id, body)
      setMsg(res.message)
      setDraft('')
      setContrib(false)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Có lỗi xảy ra.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="pbpanel">
      <div className="pbpanel__head">
        <h3 className="pbpanel__title">Lời — {current.title}</h3>
        <button type="button" className="pbpanel__link" onClick={() => setContrib((v) => !v)}>
          {contrib ? 'Huỷ' : 'Đóng góp lời'}
        </button>
      </div>

      {lyrics ? (
        <pre className="pbpanel__lyrics">{lyrics}</pre>
      ) : (
        <p className="pbpanel__empty">Chưa có lời cho bài này. Bạn hãy đóng góp nhé!</p>
      )}

      {contrib && (
        <div className="pbpanel__contrib">
          <textarea
            className="pbpanel__textarea"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Nhập lời bài hát bạn muốn đóng góp..."
            rows={5}
            maxLength={8000}
          />
          <button
            type="button"
            className="pbpanel__submit"
            onClick={send}
            disabled={sending || !draft.trim()}
          >
            Gửi đóng góp
          </button>
        </div>
      )}
      {msg && <p className="pbpanel__msg">{msg}</p>}
    </div>
  )
}

/** Thiết bị phát (Remote Playback API — Cast/AirPlay nếu trình duyệt hỗ trợ). */
function DevicePanel() {
  const p = usePlayer()
  return (
    <div className="pbpanel">
      <h3 className="pbpanel__title">Thiết bị phát</h3>
      <div className="pbdev pbdev--cur">
        <svg viewBox="0 0 24 24" className="pbdev__icon" aria-hidden="true">
          <rect x="3" y="4" width="18" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M8 20h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <span>Trình duyệt này</span>
        <span className="pbdev__dot" aria-hidden="true" />
      </div>
      {p.remoteAvailable ? (
        <button type="button" className="pbpanel__submit" onClick={p.promptRemote}>
          Chuyển sang thiết bị khác…
        </button>
      ) : (
        <p className="pbpanel__empty">
          Không tìm thấy thiết bị phát từ xa. Nhạc đang phát trên trình duyệt này.
        </p>
      )}
    </div>
  )
}

/** Thanh phát cố định đáy màn hình (kiểu Spotify, style Eskaylation):
    shuffle, prev, play/pause, next, repeat (off/all/one), thanh tua,
    lời bài hát, hàng chờ, thiết bị phát. Phát nền nhờ <audio> ở PlayerProvider. */
export function PlayerBar() {
  const p = usePlayer()
  const [panel, setPanel] = useState<Panel>(null)
  if (!p.current) return null

  const cover = coverUrl(p.current)
  const pct = p.duration ? (p.currentTime / p.duration) * 100 : 0
  const togglePanel = (name: Panel) => setPanel((cur) => (cur === name ? null : name))

  return (
    <div className="player-bar" role="region" aria-label="Trình phát nhạc">
      {panel && (
        <div className="player-bar__panel">
          {panel === 'queue' && <QueuePanel />}
          {panel === 'lyrics' && <LyricsPanel />}
          {panel === 'device' && <DevicePanel />}
        </div>
      )}

      <div className="player-bar__inner">
        {/* Trái: bài đang phát */}
        <div className="player-bar__now">
          {cover ? (
            <img className="player-bar__cover" src={cover} alt="" />
          ) : (
            <span className="player-bar__cover player-bar__cover--empty" />
          )}
          <div className="player-bar__meta">
            <span className="player-bar__title">{p.current.title}</span>
            <span className="player-bar__artist">{artistOf(p.current)}</span>
          </div>
        </div>

        {/* Giữa: điều khiển + tua */}
        <div className="player-bar__center">
          <div className="player-bar__controls">
            <button
              type="button"
              className={p.shuffle ? 'pbtn pbtn--on' : 'pbtn'}
              onClick={p.toggleShuffle}
              aria-pressed={p.shuffle}
              aria-label="Phát ngẫu nhiên"
              title="Trộn bài"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M3 7h4l3 4M3 17h4l10-13h4M14 4h4M17 20h-4l-3-4M17 20l3 0M18 17l3 3-3 3"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            <button
              type="button"
              className="pbtn"
              onClick={p.prev}
              aria-label="Bài trước"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 5v14M20 5v14l-11-7z" fill="currentColor" />
              </svg>
            </button>

            <button
              type="button"
              className="pbtn pbtn--play"
              onClick={p.toggle}
              aria-label={p.isPlaying ? 'Tạm dừng' : 'Phát'}
            >
              {p.isPlaying ? (
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <rect x="6" y="5" width="4" height="14" fill="currentColor" />
                  <rect x="14" y="5" width="4" height="14" fill="currentColor" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                </svg>
              )}
            </button>

            <button
              type="button"
              className="pbtn"
              onClick={p.next}
              aria-label="Bài sau"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M17 5v14M4 5v14l11-7z" fill="currentColor" />
              </svg>
            </button>

            <button
              type="button"
              className={p.repeat !== 'off' ? 'pbtn pbtn--on' : 'pbtn'}
              onClick={p.cycleRepeat}
              aria-label={
                p.repeat === 'one' ? 'Lặp lại một bài' : p.repeat === 'all' ? 'Lặp lại tất cả' : 'Không lặp'
              }
              title={
                p.repeat === 'one' ? 'Lặp lại một bài' : p.repeat === 'all' ? 'Lặp lại tất cả' : 'Không lặp'
              }
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M17 3l3 3-3 3M7 21l-3-3 3-3M20 6H8a4 4 0 0 0-4 4v1M4 18h12a4 4 0 0 0 4-4v-1"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {p.repeat === 'one' && <span className="pbtn__badge">1</span>}
            </button>
          </div>

          <div className="player-bar__seek">
            <span className="player-bar__time">{fmt(p.currentTime)}</span>
            <input
              type="range"
              className="player-bar__range"
              min={0}
              max={p.duration || 0}
              step={0.1}
              value={p.currentTime}
              onChange={(e) => p.seek(Number(e.target.value))}
              style={{ '--pct': `${pct}%` } as CSSProperties}
              aria-label="Tua bài hát"
            />
            <span className="player-bar__time">{fmt(p.duration)}</span>
          </div>
        </div>

        {/* Phải: lời, hàng chờ, thiết bị, đóng */}
        <div className="player-bar__right">
          <button
            type="button"
            className={panel === 'lyrics' ? 'pbtn pbtn--sm pbtn--on' : 'pbtn pbtn--sm'}
            onClick={() => togglePanel('lyrics')}
            aria-label="Lời bài hát"
            title="Lời bài hát"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>

          <button
            type="button"
            className={panel === 'queue' ? 'pbtn pbtn--sm pbtn--on' : 'pbtn pbtn--sm'}
            onClick={() => togglePanel('queue')}
            aria-label="Hàng chờ"
            title="Hàng chờ"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 6h11M4 12h11M4 18h7M17 15v6l4-3z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <button
            type="button"
            className={
              panel === 'device' || p.remoteAvailable
                ? 'pbtn pbtn--sm pbtn--on'
                : 'pbtn pbtn--sm'
            }
            onClick={() => togglePanel('device')}
            aria-label="Thiết bị phát"
            title="Thiết bị phát"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="4" width="18" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path d="M8 20h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>

          <button
            type="button"
            className="pbtn pbtn--sm"
            onClick={p.stop}
            aria-label="Đóng trình phát"
            title="Đóng trình phát"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" />
              <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
