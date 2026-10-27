import { useId, useState } from 'react'
import { api } from '../api/client'
import { useLiveApi } from '../api/useLiveApi'
import { creditGroups, creditMember, type CreditMember } from '../homepage'
import type { MediaOut } from '../api/types'
import hero1 from '../assets/figma/hero-1-4ee723.png'
import hero2 from '../assets/figma/hero-2-25801d.png'
import hero3 from '../assets/figma/hero-3-5a4166.png'
import hero4 from '../assets/figma/hero-4-575400.png'
import hero5 from '../assets/figma/hero-5-1f00f4.png'
import './Home.css'

const HERO_IMAGES = [hero1, hero2, hero3, hero4, hero5]

const DEFAULT_INTRO =
  'Là cộng đồng được thành hình bởi một người. Họ gọi anh là huyền thoại. ' +
  'Âm nhạc của anh là một người bạn đồng hành trong cuộc sống của chúng tôi, ' +
  'ít nhất là một giai đoạn nào đó trong đời. Website này do cộng đồng thành ' +
  'lập nhằm lưu giữ kỉ niệm.'

const DEFAULT_MAINTAIN = [
  'Quỹ: Forever Eskay',
  'Nội dung CK: Fes',
  'Được “sao kê" ở phần comment bài viết này',
]

const THANKS = [
  'Tất cả những người đã đăng tải âm nhạc và tư liệu trước đó',
  'Những người đóng góp về công sức',
  'Những người đóng góp về tài chính',
  'Tất cả những người ủng hộ và chờ đón',
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

/* Show the main member and expand the remaining names without placeholder rows. */
function MemberAvatar({ member, media, className }: { member: CreditMember; media: MediaOut[]; className: string }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const image = media.find((asset) => asset.media_id === member.media_id && asset.mime_type.startsWith('image/'))
  const url = image?.original_url || image?.url
  return <span className={className} aria-hidden="true">
    {url && url !== failedUrl ? <img src={url} alt="" loading="lazy" onError={() => setFailedUrl(url)} /> : initials(member.name)}
  </span>
}

function RoleColumn({ role, members, media }: { role: string; members: CreditMember[]; media: MediaOut[] }) {
  const [expanded, setExpanded] = useState(false)
  const membersId = useId()
  const main = members[0]
  const rest = members.slice(1)
  return (
    <div className="home__role">
      <h3 className="home__role-title">{role}</h3>
      <div className="home__role-members">
        <div className="home__member">
          <div className="home__member-text">
            <span className="home__member-name">{main.name}</span>
            <span className="home__member-sub">{role}</span>
          </div>
          <MemberAvatar className="home__member-avatar" member={main} media={media} />
        </div>
        <div id={membersId} className="home__role-members" hidden={!expanded}>
          {rest.map((member, index) => <div className="home__member" key={`${member.name}-${index}`}>
          <div className="home__member-text">
            <span className="home__member-name home__member-name--sm">
              {member.name}
            </span>
            <span className="home__member-sub home__member-sub--sm">{role}</span>
          </div>
          <MemberAvatar
            className="home__member-avatar home__member-avatar--sm"
            member={member} media={media}
          />
          </div>)}
        </div>
        {rest.length > 0 && (
          <button
            type="button"
            className="home__role-chevron"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Thu gọn' : 'Xem thêm'}
            aria-expanded={expanded}
            aria-controls={membersId}
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

function initials(name: string) {
  return name.replace(/\(.*?\)/gu, '').trim().split(/\s+/u).map((part) => part[0]).slice(-2).join('').toLocaleUpperCase('vi')
}

export function Home() {
  const state = useLiveApi(() => api.homepage())
  const body = (state.status === 'success' ? state.data.body : {}) as Record<
    string,
    unknown
  >

  const intro = typeof body.intro === 'string' && body.intro.trim() ? body.intro : DEFAULT_INTRO
  const media = state.status === 'success' ? state.data.media : []
  const credits = creditGroups(body.credits)
    .map((group) => ({ role: group.role.trim(), members: group.members.filter((member) => member.name.trim()) }))
    .filter((group) => group.role && group.members.length > 0)
  const leader = Object.hasOwn(body, 'leader') ? creditMember(body.leader) : { name: 'Cỏ Nhỏ (Huyền Trang)' }
  const avatarIds = new Set([
    leader?.media_id,
    ...credits.flatMap((group) => group.members.map((member) => member.media_id)),
  ].filter((id) => id !== undefined))
  const uploadedImages = media.filter((m) => m.mime_type.startsWith('image/') && m.url && (m.media_id == null || !avatarIds.has(m.media_id))).map((m) => m.original_url || m.url)
  const heroImages = uploadedImages.length ? uploadedImages : HERO_IMAGES
  const maintain = Array.isArray(body.maintain)
    ? body.maintain.filter((line): line is string => typeof line === 'string')
    : DEFAULT_MAINTAIN

  return (
    <div className="home">
      {/* 2 đốm sáng blur (texture nền nằm ở Layout) — bọc trong vùng CLIP
          full-viewport để orbs KHÔNG tràn ngang gây cuộn/xô layout. */}
      <div className="home__decor" aria-hidden="true">
        <span className="home__orb home__orb--soft" />
        <span className="home__orb home__orb--sharp" />
      </div>

      {/* Hero: dải 5 ảnh + tên + nút cuộn (Figma #1:203) */}
      <section className="home__hero">
        <div className="home__hero-strip" aria-hidden="true">
          {/* Băng chuyền chạy ngang trái -> phải; nhân đôi ảnh để loop liền mạch */}
          <div className="home__hero-track">
            {[...heroImages, ...heroImages].map((src, i) => (
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

      {/* TRI ÂN (Figma #1:310) */}
      <section className="home__credits">
        <header className="home__section-title">
          <h2>TRI ÂN</h2>
          <p>Xin gửi lời cảm ơn chân thành đến những người đã cùng tạo ra trang web này cho cộng đồng ESKAYLATION</p>
        </header>

        <div className="home__credits-body">
          {leader?.name.trim() && <div className="home__leader">
            <div className="home__leader-text">
              <span className="home__leader-name">{leader.name}</span>
              <span className="home__leader-role">Người sáng lập, kết nối nguồn lực, xây dựng website</span>
            </div>
            <MemberAvatar className="home__avatar" member={leader} media={media} />
          </div>}

          {credits.length > 0 && <div className="home__roles">
            {credits.map((c, index) => (
              <RoleColumn key={`${c.role}-${index}`} role={c.role} members={c.members} media={media} />
            ))}
          </div>}
        </div>

        <ul className="home__thanks">
          {THANKS.map((line) => <li key={line}>{line}</li>)}
        </ul>
        <p className="home__thanks-dsk">CẢM ƠN DSK</p>
      </section>

      {/* Maintain Website (Figma #1:363) */}
      <section className="home__maintain">
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
