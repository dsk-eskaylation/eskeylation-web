"""Regressions for the social release, using generated media and API fixtures."""

import io
import wave
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from playwright.sync_api import expect


def _item(i, kind="community"):
    return {
        "id": i,
        "type": kind,
        "title": f"Review item {i}",
        "slug": f"review-{i}",
        "summary": f"Review caption {i}",
        "body": {"author": "Review tester"},
        "published_at": "2026-10-29T00:00:00Z",
        "media": [
            {
                "media_id": i,
                "url": "/fixture.png",
                "mime_type": "image/png",
                "width": 640,
                "height": 480,
                "caption": None,
                "alt_text": None,
                "is_primary": True,
                "duration": None,
            }
        ],
    }


def _page(items, total=None, page=1, size=20):
    total = len(items) if total is None else total
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": size,
        "pages": (total + size - 1) // size,
    }


def _comment(i, cid):
    return {
        "id": i,
        "content_id": cid,
        "body": f"Comment {i} on song {cid}",
        "author_name": "Review",
        "created_at": "2026-10-29T00:00:00Z",
        "updated_at": "2026-10-29T00:00:00Z",
        "edited": False,
        "reactions": {"counts": {}, "total": 0, "my_reaction": None},
        "is_mine": True,
    }


def _fixture(base, context):
    ctx = context()
    page = ctx.new_page()
    state = {
        "revision": "1",
        "calls": [],
        "submitted": None,
        "errors": [],
        "upload_error": True,
        "feed_error_once": False,
        "profile_error": False,
    }
    page.on("pageerror", lambda error: state["errors"].append(str(error)))
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), "orange").save(buf, format="PNG")
    png = buf.getvalue()

    def route(r):
        u = urlsplit(r.request.url)
        path, q = u.path, parse_qs(u.query)
        state["calls"].append(path + "?" + u.query)
        if not r.request.url.startswith(base + "/"):
            return r.abort()
        if path == "/fixture.png":
            return r.fulfill(body=png, content_type="image/png")
        if not path.startswith(("/api/", "/auth/")):
            return r.continue_()
        data, status = {}, 200
        if path == "/auth/session":
            data = {
                "id": 1,
                "email": "review@test.dev",
                "role": "member",
                "is_active": True,
            }
        elif path == "/api/catalog":
            data = {"revision": state["revision"]}
        elif path == "/api/me/notifications":
            data = {"unread": 0, "items": []}
        elif path in {"/api/me/posts", "/api/me/saved"}:
            n = int(q.get("page", ["1"])[0])
            kind = q.get("type", ["community"])[0]
            data = _page(
                [
                    _item(i, kind)
                    for i in range((n - 1) * 100 + 1, min(n * 100, 201) + 1)
                ],
                201,
                n,
                100,
            )
            if n == 2 and state["profile_error"]:
                data, status = {"detail": "Fixture unavailable"}, 503
        elif path == "/api/community/uploads":
            data, status = (
                ({"detail": "Fixture upload failure"}, 503)
                if state["upload_error"]
                else ({"id": 991, "url": "/fixture.png"}, 201)
            )
        elif path == "/api/community/posts":
            state["submitted"] = r.request.post_data_json
            data, status = {"message": "Review fixture submitted"}, 201
        elif path == "/api/community":
            if state["feed_error_once"]:
                state["feed_error_once"] = False
                return r.fulfill(status=503, json={"detail": "Temporary feed outage"})
            n = int(q.get("page", ["1"])[0])
            ids = [
                i for i in range(1, 41) if not (i == 25 and state["revision"] == "2")
            ]
            data = _page([_item(i) for i in ids[(n - 1) * 20 : n * 20]], len(ids), n)
        elif path.endswith("/interactions"):
            data = {
                "content_id": 1,
                "reactions": {"counts": {}, "total": 0, "my_reaction": None},
                "comment_count": 0,
                "saved": False,
            }
        elif path.endswith("/comments"):
            data = _page([])
        elif path == "/api/homepage":
            data = _item(999, "homepage")
        else:
            data = _page([])
        r.fulfill(status=status, json=data)

    ctx.route("**/*", route)
    ctx.route_web_socket("**/*", lambda ws: None)
    return ctx, page, state, png


def check_social_release(base, context, passed, evidence):
    ctx, page, state, _ = _fixture(base, context)
    try:
        page.goto(base + "/profile", wait_until="networkidle")
        expect(page.locator(".profile__stats strong")).to_have_text(
            ["201", "201", "201"]
        )
        for label, selector in [
            ("Bài đăng", ".profile__grid > li"),
            ("Yêu thích", ".profile__songs > li"),
            ("Đã lưu", ".profile__grid > li"),
        ]:
            page.get_by_role("tab", name=label, exact=True).click()
            expect(page.locator(selector)).to_have_count(100)
            state["profile_error"] = True
            page.get_by_role("button", name="Xem thêm", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("Không tải được")
            expect(page.locator(selector)).to_have_count(100)
            state["profile_error"] = False
            page.get_by_role("button", name="Thử lại", exact=True).click()
            expect(page.locator(selector)).to_have_count(200)
            page.get_by_role("button", name="Xem thêm", exact=True).click()
            expect(page.locator(selector)).to_have_count(201)
            expect(
                page.get_by_role("button", name="Xem thêm", exact=True)
            ).to_have_count(0)
        assert not state["errors"]
        passed(
            "Profile pages all 201 posts/favorites/saved items, "
            "reports totals and retries failures"
        )
    finally:
        ctx.close()

    ctx, page, state, png = _fixture(base, context)
    try:
        page.goto(base + "/community", wait_until="networkidle")
        page.get_by_role("button", name="Bạn đang nghĩ gì về ESKAYLATION?").click()
        dialog = page.get_by_role("dialog", name="Tạo bài viết")
        dialog.get_by_label("Nội dung bài viết").fill("Review photo post")
        file = {"name": "test.png", "mimeType": "image/png", "buffer": png}
        dialog.locator("input[type=file]").set_input_files(file)
        expect(dialog.locator(".composer__image--error")).to_have_count(1)
        expect(dialog.get_by_role("button", name="Đăng", exact=True)).to_be_disabled()
        assert state["submitted"] is None
        dialog.get_by_role("button", name="Gỡ ảnh test.png").click()
        state["upload_error"] = False
        dialog.locator("input[type=file]").set_input_files(file)
        expect(dialog.locator(".composer__image--done")).to_have_count(1)
        dialog.get_by_role("button", name="Đăng", exact=True).click()
        expect(dialog).to_have_count(0)
        assert state["submitted"]["media_ids"] == [991]
        assert not state["errors"]
        passed(
            "Failed member image upload blocks posting "
            "until the failed image is replaced"
        )
    finally:
        ctx.close()

    ctx, page, state, _ = _fixture(base, context)
    try:
        page.goto(base + "/community", wait_until="networkidle")
        expect(page.locator(".community__feed > .cpost")).to_have_count(20)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        expect(page.locator(".community__feed > .cpost")).to_have_count(40)
        stale = page.locator(".community__feed > .cpost").filter(
            has_text="Review caption 25"
        )
        stale.locator(".cpost__cell").first.click()
        expect(page.locator(".cpost--detail")).to_be_visible()
        state["revision"] = "2"
        state["feed_error_once"] = True
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        expect(page.locator(".community__feed > .cpost")).to_have_count(
            39, timeout=15000
        )
        expect(stale).to_have_count(0)
        expect(page.locator(".cpost--detail")).to_have_count(0)
        assert not state["errors"]
        passed(
            "Catalog changes refresh older feed pages and close a removed post dialog"
        )
    finally:
        ctx.close()

    ctx, page, state, _ = _fixture(base, context)
    try:
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 8000 * 30)
        tracks = [_item(101, "music"), _item(102, "music")]
        for track in tracks:
            track["body"]["audio_url"] = "/tone.wav"
        ctx.route(
            "**/tone.wav",
            lambda r: r.fulfill(body=audio.getvalue(), content_type="audio/wav"),
        )
        ctx.route("**/api/music?*", lambda r: r.fulfill(json=_page(tracks, size=60)))
        ctx.route("**/api/albums", lambda r: r.fulfill(json=[]))
        pending = []
        failure = {"more": True}

        def comments(r):
            u = urlsplit(r.request.url)
            cid = int(u.path.split("/")[3])
            cursor = int(parse_qs(u.query).get("after_id", ["0"])[0])
            if r.request.method == "POST":
                pending.append(r)
            elif cursor and failure["more"]:
                r.fulfill(status=503, json={"detail": "Fixture failure"})
            else:
                rows = (
                    [
                        _comment(i, cid)
                        for i in range(cursor + 1, min(cursor + 50, 51) + 1)
                    ]
                    if cid == 101
                    else []
                )
                r.fulfill(json=_page(rows, total=51 if cid == 101 else 0, size=50))

        ctx.route("**/api/community/*/comments*", comments)
        page.goto(base + "/music", wait_until="networkidle")
        page.get_by_role("button", name="Phát Review item 101", exact=True).last.click()
        bar = page.get_by_role("region", name="Trình phát nhạc")
        bar.get_by_role("button", name="Bình luận", exact=True).click()
        expect(page.locator(".pbpanel__comments li")).to_have_count(50)
        page.get_by_role("button", name="Xem thêm bình luận").click()
        expect(page.get_by_role("button", name="Thử lại bình luận")).to_be_visible()
        expect(page.locator(".pbpanel__comments li")).to_have_count(50)
        failure["more"] = False
        page.get_by_role("button", name="Thử lại bình luận").click()
        expect(page.locator(".pbpanel__comments li")).to_have_count(51)
        passed(
            "Music comment cursor loads beyond 50 without loss or duplicates "
            "and retries errors"
        )
        page.get_by_label("Viết bình luận", exact=True).fill(
            "Delayed comment for song A"
        )
        page.get_by_role("button", name="Gửi bình luận", exact=True).click()
        page.wait_for_timeout(100)
        assert len(pending) == 1
        bar.get_by_role("button", name="Bài sau", exact=True).click()
        expect(page.locator(".pbpanel__title")).to_contain_text("Review item 102")
        expect(page.locator(".pbpanel__comments li")).to_have_count(0)
        old = _comment(999, 101)
        old["body"] = "Delayed comment for song A"
        pending[0].fulfill(status=201, json=old)
        page.wait_for_timeout(250)
        expect(page.locator(".pbpanel__comments li")).to_have_count(0)
        expect(page.get_by_label("Viết bình luận", exact=True)).to_have_value("")
        assert not state["errors"]
        passed(
            "A late comment response cannot enter the next song's panel "
            "or carry its draft"
        )
    finally:
        ctx.close()

    ctx, page, state, _ = _fixture(base, context)
    try:
        homepage = _item(999, "homepage")
        homepage["body"] = {
            "leader": None,
            "product": {"name": "Fixture product", "media_id": 2},
            "support": {"qr_media_id": 3},
        }
        homepage["media"] = [
            {**_item(i)["media"][0], "url": f"/fixture.png?kind={name}"}
            for i, name in [(1, "hero"), (2, "product"), (3, "qr")]
        ]
        ctx.route("**/api/homepage", lambda r: r.fulfill(json=homepage))
        page.goto(base + "/", wait_until="networkidle")
        expect(page.locator(".home__hero-track img")).to_have_count(2)
        sources = page.locator(".home__hero-track img").evaluate_all(
            "els=>els.map(e=>e.getAttribute('src'))"
        )
        assert sources == ["/fixture.png?kind=hero"] * 2
        page.goto(base + "/community?tab=products", wait_until="networkidle")
        expect(page.locator(".community__card img")).to_have_attribute(
            "src", "/fixture.png?kind=product"
        )
        page.goto(base + "/community?tab=support", wait_until="networkidle")
        expect(page.locator(".community__qr")).to_have_attribute(
            "src", "/fixture.png?kind=qr"
        )
        page.screenshot(path=str(evidence / "social-support.png"))
        assert not state["errors"]
        passed(
            "Homepage hero excludes product and QR assets "
            "while Community renders each correctly"
        )
    finally:
        ctx.close()
