import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { ContentOut } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { SearchBar } from "../components/SearchBar";
import {
  usePlayer,
  audioUrl,
  coverUrl,
  artistOf,
} from "../player/PlayerContext";
import "./Music.css";

const EMPTY_ITEMS: ContentOut[] = [];
const searchable = (text: string) =>
  text
    .toLocaleLowerCase("vi")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/đ/g, "d");

/** One library and a persistent player; no genre filters or Drive audio embeds. */
export function Music() {
  const [query, setQuery] = useState("");
  const [attempt, setAttempt] = useState(0);
  const player = usePlayer();
  const state = useApi(() => api.listAll("music"), [attempt]);
  const library = state.status === "success" ? state.data.items : EMPTY_ITEMS;
  const items = useMemo(() => {
    const needle = searchable(query.trim());
    return needle
      ? library.filter((track) =>
          searchable(`${track.title} ${artistOf(track)}`).includes(needle),
        )
      : library;
  }, [library, query]);
  const featured = player.current ?? library[0];
  const isCurrent = (track: ContentOut) => player.current?.id === track.id;

  function activate(track: ContentOut) {
    if (!audioUrl(track)) return;
    if (isCurrent(track)) player.toggle();
    else {
      const queue = items.some((item) => item.id === track.id)
        ? items
        : library;
      player.playQueue(
        queue,
        queue.findIndex((item) => item.id === track.id),
      );
    }
  }

  return (
    <div className="music">
      <header className="music__heading">
        <p>ESKAYLATION AUDIO</p>
        <h1>Thư viện âm nhạc</h1>
        <span>
          {state.status === "success"
            ? `${library.length} bài hát · Chọn một bài để bắt đầu`
            : state.status === "error"
              ? "Kết nối thư viện bị gián đoạn"
              : "Đang tải thư viện…"}
        </span>
      </header>
      {state.status === "error" && (
        <div role="alert">
          <EmptyState title="Chưa tải được thư viện nhạc." />
          <button
            className="music__retry"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Thử lại
          </button>
        </div>
      )}
      {state.status === "success" && library.length === 0 && (
        <EmptyState title="Thư viện chưa có bài hát." />
      )}
      {featured && (
        <section className="music__stage" aria-label="Thư viện và trình phát">
          <div className="music__hero">
            <div className="music__cover">
              {coverUrl(featured) ? (
                <img src={coverUrl(featured)!} alt={featured.title} />
              ) : (
                <span className="music__cover-empty" aria-hidden="true" />
              )}
              <button
                type="button"
                className="music__cover-play"
                onClick={() => activate(featured)}
                disabled={!audioUrl(featured)}
                aria-label={`${isCurrent(featured) && player.isPlaying ? "Tạm dừng" : "Phát"} ${featured.title}`}
              >
                {isCurrent(featured) && player.isPlaying ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect
                      x="6"
                      y="5"
                      width="4"
                      height="14"
                      fill="currentColor"
                    />
                    <rect
                      x="14"
                      y="5"
                      width="4"
                      height="14"
                      fill="currentColor"
                    />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                  </svg>
                )}
              </button>
            </div>
            <div className="music__hero-meta">
              <h2 className="music__hero-title">{featured.title}</h2>
              <span className="music__hero-artist">{artistOf(featured)}</span>
            </div>
            <p className="music__hint">
              Nhạc tiếp tục phát khi bạn khám phá website.
            </p>
          </div>
          <aside className="music__side" aria-label="Danh sách bài hát">
            <SearchBar
              value={query}
              onChange={setQuery}
              onClear={() => setQuery("")}
              placeholder="Tìm bài hát hoặc nghệ sĩ"
            />
            <div className="music__side-head">
              <span className="music__side-label">{items.length} bài hát</span>
              <Link to="/music/all" className="music__see-all">
                Xem dạng lưới
              </Link>
            </div>
            {items.length === 0 && (
              <p role="status">Không tìm thấy bài hát. Hãy thử từ khóa khác.</p>
            )}
            <ol className="music__list">
              {items.map((track, index) => {
                const active = isCurrent(track);
                const playable = Boolean(audioUrl(track));
                return (
                  <li key={track.id}>
                    <button
                      type="button"
                      className={
                        active ? "music__row music__row--active" : "music__row"
                      }
                      onClick={() => activate(track)}
                      disabled={!playable}
                      aria-label={`${active && player.isPlaying ? "Tạm dừng" : "Phát"} ${track.title}`}
                      aria-pressed={active && player.isPlaying}
                    >
                      <span className="music__row-idx" aria-hidden="true">
                        {active && player.isPlaying ? (
                          <span className="music__eq">
                            <i />
                            <i />
                            <i />
                          </span>
                        ) : (
                          index + 1
                        )}
                      </span>
                      {coverUrl(track) ? (
                        <img
                          className="music__row-cover"
                          src={coverUrl(track)!}
                          alt=""
                          loading="lazy"
                        />
                      ) : (
                        <span
                          className="music__row-cover music__row-cover--empty"
                          aria-hidden="true"
                        />
                      )}
                      <span className="music__row-meta">
                        <span className="music__row-title">{track.title}</span>
                        <span className="music__row-artist">
                          {artistOf(track)}
                        </span>
                      </span>
                      {!playable && (
                        <span className="music__row-badge">Chưa có audio</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          </aside>
        </section>
      )}
    </div>
  );
}
