import { api } from '../api/client'
import { useApi } from '../api/useApi'
import './Home.css'

const DEFAULT_INTRO =
  'Là cộng đồng được thành hình bởi một người. Họ gọi anh là huyền thoại. ' +
  'Âm nhạc của anh là một người bạn đồng hành trong cuộc sống của chúng tôi, ' +
  'ít nhất là một giai đoạn nào đó trong đời. Website này do cộng đồng thành ' +
  'lập nhằm lưu giữ kỉ niệm.'

const DEFAULT_CREDITS = [
  { role: 'DESIGN', names: [] as string[] },
  { role: 'Development', names: [] as string[] },
  { role: 'Editor', names: [] as string[] },
]

const DEFAULT_MAINTAIN = [
  'Quỹ: Forever Eskay',
  'Nội dung CK: Fes',
  'Được “sao kê" ở phần comment bài viết này',
]

function Dots() {
  return (
    <div className="home__dots" aria-hidden="true">
      {Array.from({ length: 11 }).map((_, i) => (
        <span key={i} />
      ))}
    </div>
  )
}

export function Home() {
  const state = useApi(() => api.homepage())
  const body = (state.status === 'success' ? state.data.body : {}) as Record<
    string,
    unknown
  >

  const intro = typeof body.intro === 'string' ? body.intro : DEFAULT_INTRO
  const credits = Array.isArray(body.credits)
    ? (body.credits as typeof DEFAULT_CREDITS)
    : DEFAULT_CREDITS
  const maintain = Array.isArray(body.maintain)
    ? (body.maintain as string[])
    : DEFAULT_MAINTAIN

  return (
    <div className="home">
      <section className="home__hero">
        <h1 className="home__brand">ESKAYLATION</h1>
        <span className="home__hero-pill" aria-hidden="true" />
      </section>

      <section className="home__intro">
        <Dots />
        <p>{intro}</p>
        <Dots />
      </section>

      <section className="home__credits">
        <header className="home__section-title">
          <h2>SHOUT OUT</h2>
          <p>to the guys</p>
        </header>

        <div className="home__leader">
          <div className="home__leader-text">
            <span className="home__leader-name">Cỏ nhỏ</span>
            <span className="home__leader-role">Leader</span>
          </div>
          <div className="home__avatar" />
        </div>

        <div className="home__roles">
          {credits.map((c) => (
            <div className="home__role" key={c.role}>
              <span className="home__role-title">{c.role}</span>
              <ul className="home__role-names">
                {c.names.length === 0 ? (
                  <li className="muted">—</li>
                ) : (
                  c.names.map((n) => <li key={n}>{n}</li>)
                )}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="home__maintain">
        <header className="home__section-title">
          <h2>Maintain</h2>
          <p>Website</p>
        </header>
        <div className="home__maintain-info">
          {maintain.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </section>

      <div className="home__respect" aria-hidden="true">
        Respect.
      </div>
    </div>
  )
}
