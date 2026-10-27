import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { ContentOut } from "../api/types";
import { MediaImage } from "./MediaImage";
import {
  community,
  communityWsUrl,
  type CommentOut,
  type CommunityEvent,
  type InteractionOut,
  type ReactionKind,
} from "../api/community";
import { useToast } from "./Toast";
import { PostGallery } from "./PostGallery";
import { Modal } from "./Modal";
import { ReactionControl } from "./ReactionControl";
import {
  BookmarkIcon,
  CommentIcon,
  ReactionIcon,
  REACTION_COLOR,
  REACTION_ORDER,
} from "./reactionIcons";
import "./CommunityPost.css";
import { adminApi } from "../api/admin";

function fmtDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}
function fmtTime(iso: string) {
  const d = new Date(iso);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")} ${fmtDate(iso)}`;
}

/** Emoji tóm tắt cảm xúc (top 3 loại) + tổng — dùng cho bài & bình luận. */
function ReactionSummaryChips({
  counts,
  total,
}: {
  counts: Record<string, number>;
  total: number;
}) {
  const top = REACTION_ORDER.filter((k) => counts[k] > 0)
    .sort((a, b) => counts[b] - counts[a])
    .slice(0, 3);
  if (total <= 0) return null;
  return (
    <span className="cpost__stats-emojis">
      {top.map((k) => (
        <span
          key={k}
          className="cpost__stats-icon"
          style={{ color: REACTION_COLOR[k] }}
        >
          <ReactionIcon kind={k} />
        </span>
      ))}
      <span className="cpost__stats-count">{total}</span>
    </span>
  );
}

/** Thẻ bài cộng đồng kiểu Facebook (giữ style Eskaylation):
    header + caption + ảnh, thanh cảm xúc (6 loại), lưu bài, và khu bình luận
    realtime (WebSocket) — mỗi bình luận có cảm xúc riêng + sửa/xoá cho chủ nhân. */
export function CommunityPost({
  content,
  loggedIn,
  isAdmin = false,
  priority = false,
}: {
  content: ContentOut;
  loggedIn: boolean;
  isAdmin?: boolean;
  priority?: boolean;
}) {
  const id = content.id;
  const { notify } = useToast();
  const author =
    typeof content.body.author === "string"
      ? content.body.author
      : content.title;

  const [inter, setInter] = useState<InteractionOut | null>(null);
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const loginHref = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
  const goLogin = () => navigate(loginHref);
  const [comments, setComments] = useState<CommentOut[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [viewingMedia, setViewingMedia] = useState(false);
  const articleRef = useRef<HTMLElement>(null);
  const [hasMoreComments, setHasMoreComments] = useState(false);
  const [commentsBusy, setCommentsBusy] = useState(false);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const commentsCursor = useRef<number | undefined>(undefined);
  const commentsLoading = useRef(false);
  const seenComments = useRef(new Set<number>());
  const removedComments = useRef(new Set<number>());

  useEffect(() => {
    let alive = true;
    const load = () => {
      void community
        .interactions(id)
        .then((d) => alive && setInter(d))
        .catch(() => {});
    };
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(
            (entries) => {
              if (entries.some((entry) => entry.isIntersecting)) {
                observer?.disconnect();
                load();
              }
            },
            { rootMargin: "400px" },
          );
    if (observer && articleRef.current) observer.observe(articleRef.current);
    else load();
    return () => {
      alive = false;
      observer?.disconnect();
    };
  }, [id]);

  // Tải bình luận + mở WebSocket khi khu bình luận được mở
  useEffect(() => {
    if (!expanded) return;
    let alive = true;
    setCommentsBusy(true);
    setCommentsError(null);
    commentsLoading.current = true;
    community.comments(id).then((page) => {
      if (!alive) return;
      commentsCursor.current = page.items.at(-1)?.id;
      setHasMoreComments(page.items.length === 50);
      page.items.forEach((comment) => seenComments.current.add(comment.id));
      setComments((current) => mergeComments(current, page.items));
    }).catch(() => {
      if (alive) setCommentsError("Chưa tải được bình luận. Hãy thử lại.");
    }).finally(() => {
      if (alive) { setCommentsBusy(false); commentsLoading.current = false; }
    });

    const ws = new WebSocket(communityWsUrl(id));
    // Keep comments current when the reverse proxy cannot upgrade WebSocket.
    // Reconcile while visible, including events missed during a Redis outage.
    let refreshing = false;
    const poll = window.setInterval(() => {
      if (
        !alive ||
        refreshing ||
        document.hidden ||
        commentsLoading.current
      )
        return;
      refreshing = true;
      const refresh = async () => {
        const boundary = commentsCursor.current;
        const loaded: CommentOut[] = [];
        let cursor: number | undefined;
        do {
          const page = await community.comments(id, 1, cursor);
          loaded.push(...page.items);
          cursor = page.items.at(-1)?.id;
          if (page.items.length < 50 || cursor === undefined) break;
        } while (boundary !== undefined && cursor < boundary);
        const summary = await community.interactions(id);
        if (!alive) return;
        loaded.forEach((comment) => seenComments.current.add(comment.id));
        // Preserve socket comments newer than the fetched boundary.
        const last = loaded.at(-1)?.id ?? 0;
        setComments((current) => mergeComments(current.filter((c) => c.id > Math.max(boundary ?? 0, last)), loaded));
        setInter(summary);
      };
      void refresh().catch(() => {}).finally(() => { refreshing = false; });

    }, 15000);
    ws.onmessage = (e) => {
      if (!alive) return;
      let ev: CommunityEvent;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      if (ev.kind === "comment") appendComment(ev.comment);
      else if (ev.kind === "comment_edit")
        setComments((cur) =>
          cur.map((c) =>
            c.id === ev.comment.id
              ? {
                  ...c,
                  body: ev.comment.body,
                  updated_at: ev.comment.updated_at,
                  edited: ev.comment.edited,
                }
              : c,
          ),
        );
      else if (ev.kind === "comment_delete")
        removeCommentLocally(ev.comment_id);
      else if (ev.kind === "reaction")
        setInter((cur) =>
          cur
            ? {
                ...cur,
                reactions: {
                  ...cur.reactions,
                  counts: ev.counts,
                  total: ev.total,
                },
              }
            : cur,
        );
    };
    return () => {
      alive = false;
      window.clearInterval(poll);
      ws.close();
      commentsLoading.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, id]);

  function mergeComments(current: CommentOut[], incoming: CommentOut[]) {
    const byId = new Map(current.map((c) => [c.id, c]));
    incoming.forEach((c) => { if (!removedComments.current.has(c.id)) byId.set(c.id, c); });
    return [...byId.values()].sort((a, b) => a.id - b.id);
  }

  async function loadMoreComments() {
    if (commentsLoading.current) return;
    commentsLoading.current = true;
    setCommentsBusy(true);
    setCommentsError(null);
    try {
      const page = await community.comments(id, 1, commentsCursor.current);
      commentsCursor.current = page.items.at(-1)?.id ?? commentsCursor.current;
      setHasMoreComments(page.items.length === 50);
      page.items.forEach((comment) => seenComments.current.add(comment.id));
      setComments((current) => mergeComments(current, page.items));
    } catch {
      setCommentsError("Chưa tải được bình luận. Hãy thử lại.");
    } finally {
      commentsLoading.current = false;
      setCommentsBusy(false);
    }
  }

  function appendComment(c: CommentOut) {
    if (removedComments.current.has(c.id)) return;
    if (seenComments.current.has(c.id)) {
      // The socket can arrive before our POST response with is_mine=true.
      if (c.is_mine)
        setComments((cur) => cur.map((item) => (item.id === c.id ? c : item)));
      return;
    }
    seenComments.current.add(c.id);
    setComments((cur) => [...cur, c]);
    setInter((cur) =>
      cur ? { ...cur, comment_count: cur.comment_count + 1 } : cur,
    );
  }

  function removeCommentLocally(commentId: number) {
    if (removedComments.current.has(commentId)) return;
    removedComments.current.add(commentId);
    seenComments.current.delete(commentId);
    setComments((cur) => cur.filter((comment) => comment.id !== commentId));
    setInter((cur) =>
      cur ? { ...cur, comment_count: Math.max(0, cur.comment_count - 1) } : cur,
    );
  }

  function patchComment(commentId: number, patch: Partial<CommentOut>) {
    setComments((cur) =>
      cur.map((c) => (c.id === commentId ? { ...c, ...patch } : c)),
    );
  }

  // ---- Cảm xúc bài ----
  async function postPick(kind: ReactionKind) {
    try {
      const summary =
        inter?.reactions.my_reaction === kind
          ? await community.unreact(id)
          : await community.react(id, kind);
      setInter((cur) => (cur ? { ...cur, reactions: summary } : cur));
    } catch {
      /* bỏ qua */
    }
  }
  async function postToggle() {
    if (!inter) return;
    await (inter.reactions.my_reaction
      ? postPick(inter.reactions.my_reaction)
      : postPick("like"));
  }

  async function toggleSave() {
    if (!inter) return;
    try {
      const res = inter.saved
        ? await community.unsave(id)
        : await community.save(id);
      setInter((cur) => (cur ? { ...cur, saved: res.saved } : cur));
    } catch {
      /* bỏ qua */
    }
  }

  // ---- Bình luận: gửi / sửa / xoá / cảm xúc ----
  async function submitComment(e: FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const c = await community.addComment(id, body);
      appendComment(c);
      setDraft("");
    } catch (err) {
      // Hiện cảnh báo (vd bị chặn vì chứa từ cấm) thay vì im lặng
      notify(err instanceof Error ? err.message : "Không gửi được bình luận", {
        tone: "error",
      });
    } finally {
      setSending(false);
    }
  }

  async function saveEdit(c: CommentOut) {
    const body = editDraft.trim();
    if (!body) return;
    try {
      const updated = await community.editComment(id, c.id, body);
      patchComment(c.id, {
        body: updated.body,
        updated_at: updated.updated_at,
        edited: updated.edited,
      });
      setEditingId(null);
      setEditDraft("");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Không sửa được bình luận", {
        tone: "error",
      });
    }
  }

  async function removeComment(c: CommentOut) {
    if (!window.confirm("Xoá bình luận này?")) return;
    try {
      await community.deleteComment(id, c.id);
      removeCommentLocally(c.id);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Không xoá được bình luận", {
        tone: "error",
      });
    }
  }

  async function adminRemoveComment(c: CommentOut) {
    if (!window.confirm(`Xoá bình luận của ${c.author_name}?`)) return;
    try {
      await adminApi.deleteComment(c.id);
      removeCommentLocally(c.id);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Không xoá được bình luận", {
        tone: "error",
      });
    }
  }

  async function commentReact(c: CommentOut, kind: ReactionKind) {
    try {
      const summary =
        c.reactions.my_reaction === kind
          ? await community.unreactComment(id, c.id)
          : await community.reactComment(id, c.id, kind);
      patchComment(c.id, { reactions: summary });
    } catch {
      /* bỏ qua */
    }
  }

  const counts = inter?.reactions.counts ?? {};
  const total = inter?.reactions.total ?? 0;
  const mine = inter?.reactions.my_reaction ?? null;
  const media = content.media;

  return (
    <article ref={articleRef} className="cpost">
      <header className="cpost__head">
        <span className="cpost__avatar" aria-hidden="true" />
        <div className="cpost__id">
          <span className="cpost__name">{author}</span>
          <div className="cpost__meta">
            <time>{fmtDate(content.published_at)}</time>
            <span className="cpost__dot" aria-hidden="true" />
            <span>Cộng đồng</span>
          </div>
        </div>
      </header>

      {content.summary && <p className="cpost__caption">{content.summary}</p>}

      {media.length > 0 && (
        <div
          className={`cpost__media cpost__media--n${Math.min(media.length, 4)}`}
        >
          {media.slice(0, 4).map((m, i) => (
            <button
              type="button"
              className="cpost__cell"
              key={i}
              onClick={() => setViewingMedia(true)}
              aria-label={`Xem ${content.title}`}
            >
              {m.url ? (
                <MediaImage
                  media={m}
                  alt={m.alt_text ?? content.title}
                  sizes="(max-width: 640px) calc(100vw - 32px), 600px"
                  loading={priority && i === 0 ? "eager" : "lazy"}
                  fetchPriority={priority && i === 0 ? "high" : "auto"}
                />
              ) : (
                <span>Xem tư liệu</span>
              )}
              {m.mime_type.startsWith("video/") && (
                <span className="cpost__more">▶</span>
              )}
              {i === 3 && media.length > 4 && (
                <span className="cpost__more">+{media.length - 4}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {viewingMedia && (
        <Modal onClose={() => setViewingMedia(false)} label="Ảnh và video bài viết" showClose>
          <PostGallery content={content} />
        </Modal>
      )}

      {/* Tổng quan reactions + số bình luận */}
      {(total > 0 || (inter?.comment_count ?? 0) > 0) && (
        <div className="cpost__stats">
          <ReactionSummaryChips counts={counts} total={total} />
          {(inter?.comment_count ?? 0) > 0 && (
            <button
              type="button"
              className="cpost__stats-comments"
              onClick={() => setExpanded(true)}
            >
              {inter?.comment_count} bình luận
            </button>
          )}
        </div>
      )}

      {/* Thanh hành động */}
      <div className="cpost__actions">
        <ReactionControl
          variant="post"
          mine={mine}
          onToggle={loggedIn ? postToggle : goLogin}
          onPick={loggedIn ? postPick : goLogin}
        />

        <button
          type="button"
          className="cpost__act"
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="cpost__act-icon">
            <CommentIcon />
          </span>
          Bình luận
        </button>

        <button
          type="button"
          className={inter?.saved ? "cpost__act cpost__act--on" : "cpost__act"}
          onClick={loggedIn ? toggleSave : goLogin}
        >
          <span className="cpost__act-icon">
            <BookmarkIcon filled={inter?.saved} />
          </span>
          {inter?.saved ? "Đã lưu" : "Lưu"}
        </button>
      </div>

      {/* Khu bình luận */}
      {expanded && (
        <div className="cpost__comments">
          {comments.length === 0 && !commentsBusy && !commentsError && (
            <p className="cpost__comments-empty">
              Chưa có bình luận. Hãy là người đầu tiên!
            </p>
          )}
          {comments.map((c) => (
            <div className="cpost__comment" key={c.id}>
              <span className="cpost__comment-avatar" aria-hidden="true" />
              <div className="cpost__comment-main">
                <div className="cpost__comment-bubble">
                  {/* Issue 4: thời gian nằm CẠNH tên người bình luận */}
                  <div className="cpost__comment-head">
                    <span className="cpost__comment-author">
                      {c.author_name}
                    </span>
                    <time className="cpost__comment-time">
                      {fmtTime(c.edited ? c.updated_at : c.created_at)}
                      {c.edited && " (đã sửa)"}
                    </time>
                  </div>
                  {editingId === c.id ? (
                    <form
                      className="cpost__edit"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void saveEdit(c);
                      }}
                    >
                      <input
                        className="cpost__input"
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        maxLength={2000}
                        autoFocus
                      />
                      <button
                        type="submit"
                        className="cpost__send"
                        disabled={!editDraft.trim()}
                      >
                        Lưu
                      </button>
                      <button
                        type="button"
                        className="cpost__edit-cancel"
                        onClick={() => {
                          setEditingId(null);
                          setEditDraft("");
                        }}
                      >
                        Huỷ
                      </button>
                    </form>
                  ) : (
                    <span className="cpost__comment-body">{c.body}</span>
                  )}
                  {c.reactions.total > 0 && (
                    <span className="cpost__comment-reactions">
                      <ReactionSummaryChips
                        counts={c.reactions.counts}
                        total={c.reactions.total}
                      />
                    </span>
                  )}
                </div>
                {/* Hàng thao tác dưới mỗi bình luận */}
                {editingId !== c.id && (
                  <div className="cpost__comment-actions">
                    {loggedIn && (
                      <ReactionControl
                        variant="comment"
                        mine={c.reactions.my_reaction}
                        onToggle={() =>
                          void commentReact(
                            c,
                            c.reactions.my_reaction ?? "like",
                          )
                        }
                        onPick={(k) => void commentReact(c, k)}
                      />
                    )}
                    {c.is_mine && (
                      <>
                        <button
                          type="button"
                          className="cpost__comment-act"
                          onClick={() => {
                            setEditingId(c.id);
                            setEditDraft(c.body);
                          }}
                        >
                          Sửa
                        </button>
                        <button
                          type="button"
                          className="cpost__comment-act cpost__comment-act--danger"
                          onClick={() => void removeComment(c)}
                        >
                          Xoá
                        </button>
                      </>
                    )}
                    {isAdmin && !c.is_mine && (
                      <button
                        type="button"
                        className="cpost__comment-act cpost__comment-act--danger"
                        onClick={() => void adminRemoveComment(c)}
                      >
                        Xoá (admin)
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {commentsBusy && <p role="status">Đang tải bình luận…</p>}
          {commentsError && <p role="alert">{commentsError}</p>}
          {(hasMoreComments || commentsError) && <button type="button" className="cpost__act" disabled={commentsBusy}
            onClick={() => void loadMoreComments()}>{commentsError ? 'Thử lại bình luận' : 'Xem thêm bình luận'}</button>}
          {loggedIn ? (
            <form className="cpost__form" onSubmit={submitComment}>
              <input
                className="cpost__input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Viết bình luận..."
                maxLength={2000}
              />
              <button
                type="submit"
                className="cpost__send"
                disabled={sending || !draft.trim()}
              >
                Gửi
              </button>
            </form>
          ) : (
            <p className="cpost__login-hint">
              <Link to={loginHref}>Đăng nhập</Link> để bình luận và bày tỏ cảm xúc.
            </p>
          )}
        </div>
      )}
    </article>
  );
}
