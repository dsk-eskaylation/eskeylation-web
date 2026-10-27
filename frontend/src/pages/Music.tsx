import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useLiveApi } from "../api/useLiveApi";
import type { ContentOut } from "../api/types";
import { albumOptions, SINGLES } from "../albums";
import { Dropdown } from "../components/Dropdown";
import { EmptyState } from "../components/EmptyState";
import { SearchBar } from "../components/SearchBar";
import {
  usePlayer,
  audioUrl,
  coverUrl,
  artistOf,
  embedUrl,
} from "../player/PlayerContext";
import "./Music.css";

const EMPTY_ITEMS: ContentOut[] = [];
const searchable = (text: string) =>
  text
    .toLocaleLowerCase("vi")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/đ/g, "d");

export function Music() {
  const [query, setQuery] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [params, setParams] = useSearchParams();
  const albumSlug = params.get("album");
  const player = usePlayer();
  const state = useLiveApi(() => api.listAll("music"), [attempt]);
  const albums = useLiveApi(() => api.albums(), [attempt]);
  // Resolve 404 as a keyed miss: useLiveApi keeps the previous album's data on errors.
  const albumDetail = useLiveApi(
    () =>
      albumSlug && albumSlug !== SINGLES
        ? api.album(albumSlug).then(
            (detail) => ({ slug: albumSlug, detail }),
            (error: unknown) => {
              if (error instanceof ApiError && error.status === 404)
                return { slug: albumSlug, detail: null };
              throw error;
            },
          )
        : Promise.resolve(null),
    [albumSlug, attempt],
  );
  const library = state.status === "success" ? state.data.items : EMPTY_ITEMS;
  const albumList = albums.status === "success" ? albums.data : [];
  const albumResult =
    albumDetail.status === "success" && albumDetail.data?.slug === albumSlug
      ? albumDetail.data
      : null;
  const album = albumResult?.detail ?? null;
  const albumFailed = albumDetail.status === "error";
  const albumMissing = albumResult !== null && !album;
  const albumPending =
    Boolean(albumSlug && albumSlug !== SINGLES) && !albumResult && !albumMissing && !albumFailed;
  const items = useMemo(() => {
    const source =
      albumSlug === SINGLES
        ? library.filter((track) => !track.album)
        : albumSlug
          ? (album?.tracks ?? EMPTY_ITEMS)
          : library;
    const needle = searchable(query.trim());
    return source.filter(
      (track) =>
        !needle || searchable(`${track.title} ${artistOf(track)}`).includes(needle),
    );
  }, [library, album, albumSlug, query]);
  const audioItems = items.filter((track) => audioUrl(track));
  const embeddedItems = items.filter((track) => embedUrl(track));
  const playableCount = audioItems.length || embeddedItems.length;
  const mixedSources = audioItems.length > 0 && embeddedItems.length > 0;
  const singles = useMemo(
    () => library.filter((track) => !track.album).length,
    [library],
  );

  function setFilter(key: "album", value: string | null) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }

  function playAll(shuffled: boolean) {
    if (audioItems.length === 0) {
      const track = embeddedItems[shuffled ? Math.floor(Math.random() * embeddedItems.length) : 0];
      if (track) player.playEmbed(track);
      return;
    }
    if (player.shuffle !== shuffled) player.toggleShuffle();
    player.playQueue(
      audioItems,
      shuffled ? Math.floor(Math.random() * audioItems.length) : 0,
    );
  }

  const featured = player.embed ?? player.current ?? items[0] ?? library[0];
  const isCurrent = (track: ContentOut) =>
    (player.embed ?? player.current)?.id === track.id;

  function activate(track: ContentOut) {
    if (!audioUrl(track)) {
      if (embedUrl(track)) player.playEmbed(track);
      return;
    }
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
                disabled={!audioUrl(featured) && !embedUrl(featured)}
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
            <div className="music__toolbar">
              <Dropdown
                label="Lọc theo album"
                value={albumSlug ?? ""}
                onChange={(value) => setFilter("album", value || null)}
                options={albumOptions(albumList, library.length, singles)}
              />
              <button
                type="button"
                className="music__tool"
                aria-label={audioItems.length ? (mixedSources ? "Phát danh sách audio" : "Phát danh sách") : "Phát bài nhúng đầu tiên"}
                onClick={() => playAll(false)}
                disabled={playableCount === 0}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M7 4.5v15l13-7.5z" fill="currentColor" />
                </svg>
                {audioItems.length ? (mixedSources ? "Phát audio" : "Phát") : "Phát bài"}
              </button>
              <button
                type="button"
                className="music__tool"
                aria-label={audioItems.length ? (mixedSources ? "Trộn danh sách audio" : "Trộn danh sách") : "Phát bài nhúng ngẫu nhiên"}
                onClick={() => playAll(true)}
                disabled={playableCount === 0}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                {audioItems.length ? (mixedSources ? "Trộn audio" : "Trộn") : "Ngẫu nhiên"}
              </button>
            </div>
            {embeddedItems.length > 0 && (
              <p className="music__hint">
                Bài SoundCloud/YouTube dùng trình phát riêng và được chọn từng bài.
                {mixedSources && ` Phát/Trộn audio áp dụng cho ${audioItems.length} bài có file âm thanh.`}
              </p>
            )}
            {(albums.status === "error" || albumFailed) && (
              <p role="alert">Không tải được album. <button type="button" className="music__retry" onClick={() => setAttempt((value) => value + 1)}>Thử lại</button></p>
            )}
            {albumMissing && (
              <p role="status">Không tìm thấy album này.</p>
            )}
            <div className="music__side-head">
              <span className="music__side-label">{items.length} bài hát</span>
              <span className="music__see-links">
                <Link to="/music/all" className="music__see-all">
                  Xem dạng lưới
                </Link>
                <Link to="/music/all?view=albums" className="music__see-all">
                  Xem lưới album
                </Link>
              </span>
            </div>
            {albumPending ? (
              <p role="status">Đang tải album…</p>
            ) : (
              !albumMissing && !albumFailed &&
              items.length === 0 && (
                <p role="status">Không tìm thấy bài hát. Hãy thử từ khóa khác.</p>
              )
            )}
            <ol className="music__list">
              {items.map((track, index) => {
                const active = isCurrent(track);
                const playable = Boolean(audioUrl(track) || embedUrl(track));
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
                          (albumSlug && track.track_no) || index + 1
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
