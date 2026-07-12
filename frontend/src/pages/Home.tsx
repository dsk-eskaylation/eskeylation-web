import { useState } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import hero1 from '../assets/figma/hero-1-4ee723.png'
import hero2 from '../assets/figma/hero-2-25801d.png'
import hero3 from '../assets/figma/hero-3-5a4166.png'
import hero4 from '../assets/figma/hero-4-575400.png'
import hero5 from '../assets/figma/hero-5-1f00f4.png'
import bgTexture from '../assets/figma/bg-texture.png'
import './Home.css'

const HERO_IMAGES = [hero1, hero2, hero3, hero4, hero5]

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

/* Dải chữ ESKAYLATION chạy ngang (Figma #1:215/#1:265) — 2 bản sao để loop liền mạch.
   JSX tĩnh hoist ra ngoài component để không phải tạo lại 22 item + 44 svg mỗi render. */
const MARQUEE_ITEMS = Array.from({ length: 11 }).map((_, i) => (
  <span className="marquee__item" key={i}>
    <svg viewBox="0 0 12 29" className="marquee__slash">
      <line x1="11" y1="1" x2="1" y2="28" stroke="currentColor" strokeWidth="1" />
    </svg>
    ESKAYLATION
    <svg viewBox="0 0 12 29" className="marquee__slash">
      <line x1="11" y1="1" x2="1" y2="28" stroke="currentColor" strokeWidth="1" />
    </svg>
  </span>
))

function Marquee({ reverse = false }: { reverse?: boolean }) {
  return (
    <div className={reverse ? 'marquee marquee--reverse' : 'marquee'}>
      <div className="marquee__strip" aria-hidden="true">
        {MARQUEE_ITEMS}
      </div>
      <div className="marquee__strip" aria-hidden="true">
        {MARQUEE_ITEMS}
      </div>
    </div>
  )
}

/* Cột vai trò (Figma #1:321): thành viên đầu rõ, hàng dưới mờ 0.22, chevron mở rộng */
function RoleColumn({ role, names }: { role: string; names: string[] }) {
  const [expanded, setExpanded] = useState(false)
  const main = names[0]
  const rest = names.slice(1)
  return (
    <div className="home__role">
      <span className="home__role-title">{role}</span>
      <div className="home__role-members">
        <div className="home__member">
          <div className="home__member-text">
            <span className="home__member-name">{main ?? '—'}</span>
            <span className="home__member-sub">{role}</span>
          </div>
          <span className="home__member-avatar" aria-hidden="true" />
        </div>
        <div
          className={
            expanded
              ? 'home__member home__member--dim home__member--open'
              : 'home__member home__member--dim'
          }
        >
          <div className="home__member-text">
            <span className="home__member-name home__member-name--sm">
              {rest[0] ?? main ?? '—'}
            </span>
            <span className="home__member-sub home__member-sub--sm">{role}</span>
          </div>
          <span
            className="home__member-avatar home__member-avatar--sm"
            aria-hidden="true"
          />
        </div>
        {rest.length > 0 && (
          <button
            type="button"
            className="home__role-chevron"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Thu gọn' : 'Xem thêm'}
          >
            <svg viewBox="0 0 20 10" className={expanded ? 'is-flipped' : ''}>
              <polyline
                points="1,1 10,9 19,1"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

export function Home() {
  const state = useApi(() => api.homepage())
  const body = (state.status === 'success' ? state.data.body : {}) as Record<
    string,
    unknown
  >

  // Luôn dùng đoạn giới thiệu mặc định, bỏ qua body.intro từ Supabase (theo yêu cầu)
  const intro = DEFAULT_INTRO
  const credits = Array.isArray(body.credits)
    ? (body.credits as typeof DEFAULT_CREDITS)
    : DEFAULT_CREDITS
  const maintain = Array.isArray(body.maintain)
    ? (body.maintain as string[])
    : DEFAULT_MAINTAIN

  return (
    <div className="home">
      {/* Lớp nền trang trí (texture + 2 đốm sáng blur) — bọc trong vùng CLIP
          full-viewport để orbs/nền KHÔNG tràn ngang gây cuộn/xô layout. */}
      <div className="home__decor" aria-hidden="true">
        <div
          className="home__bg"
          style={{ backgroundImage: `url(${bgTexture})` }}
        />
        <span className="home__orb home__orb--soft" />
        <span className="home__orb home__orb--sharp" />
      </div>

      {/* Hero: dải 5 ảnh + tên + nút cuộn (Figma #1:203) */}
      <section className="home__hero">
        <div className="home__hero-strip" aria-hidden="true">
          {/* Băng chuyền chạy ngang trái -> phải; nhân đôi ảnh để loop liền mạch */}
          <div className="home__hero-track">
            {[...HERO_IMAGES, ...HERO_IMAGES].map((src, i) => (
              <img src={src} alt="" key={i} />
            ))}
          </div>
        </div>
        <div className="home__hero-title">
          <h1 className="home__brand">ESKAYLATION</h1>
          <button
            type="button"
            className="home__scroll-pill"
            aria-label="Cuộn xuống"
            onClick={() =>
              document
                .querySelector('.home__about')
                ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }
          >
            <span className="home__scroll-mouse">
              <span className="home__scroll-dot" />
            </span>
            <svg
              className="home__scroll-chevron"
              viewBox="0 0 24 14"
              aria-hidden="true"
            >
              <polyline
                points="3,3 12,11 21,3"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </section>

      {/* Là gì? kẹp giữa 2 marquee (Figma #1:214) */}
      <section className="home__about-wrap">
        <Marquee />
        <div className="home__about">
          <div className="home__about-brand">
            <span className="home__about-name">ESKAYLATION</span>
            <span className="home__about-q">là gì?</span>
          </div>
          <p className="home__about-text">{intro}</p>
        </div>
        <Marquee reverse />
      </section>

      {/* SHOUT OUT (Figma #1:310) */}
      <section className="home__credits">
        <header className="home__section-title">
          <h2>SHOUT OUT</h2>
          <p>to the guys</p>
        </header>

        <div className="home__credits-body">
          <div className="home__leader">
            <div className="home__leader-text">
              <span className="home__leader-name">Cỏ nhỏ</span>
              <span className="home__leader-role">Leader</span>
            </div>
            <span className="home__avatar" aria-hidden="true" />
          </div>

          <div className="home__roles">
            {credits.map((c) => (
              <RoleColumn key={c.role} role={c.role} names={c.names} />
            ))}
          </div>
        </div>
      </section>

      {/* Maintain Website (Figma #1:363) */}
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
