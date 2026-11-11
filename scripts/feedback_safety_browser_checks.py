"""Feedback regressions: section isolation, legacy fund migration and URL recovery."""

import copy
import re
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect


def check_feedback_safety(base, context, passed, evidence):
    ctx = context()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    home = {
        "id": 901,
        "type": "homepage",
        "title": "Review home",
        "slug": "review-home",
        "status": "published",
        "summary": None,
        "author_id": 1,
        "created_at": "2026-11-11T00:00:00Z",
        "updated_at": "2026-11-11T00:00:00Z",
        "published_at": "2026-11-11T00:00:00Z",
        "body": {
            "intro": "Original homepage intro",
            "leader": None,
            "credits": [],
            "community_intro": "Original community intro",
            "community_rules": "Original rules",
            "sections": [{"type": "intro", "text": "Original structured section"}],
            "product": {
                "name": "Original product",
                "media_id": 902,
                "extra": "Keep product extra",
            },
            "support": {
                "amount": "3.000.000",
                "used": "Original legacy spending statement",
                "qr_media_id": 903,
                "extra": "Keep fund extra",
            },
        },
        "media": [
            {
                "media_id": i,
                "url": f"/feedback-fixture.png?asset={i}",
                "mime_type": "image/png",
                "position": n,
                "is_primary": n == 0,
                "caption": None,
            }
            for n, i in enumerate((901, 902, 903))
        ],
    }
    state = {"home": copy.deepcopy(home)}
    png = (evidence / "media/ui-image.png").read_bytes()

    def route(r):
        path = urlsplit(r.request.url).path
        if not r.request.url.startswith(base + "/"):
            return r.abort()
        if path == "/feedback-fixture.png":
            return r.fulfill(body=png, content_type="image/png")
        if path == "/missing-hero.png":
            return r.fulfill(status=404, body="missing")
        if not path.startswith(("/api/", "/auth/", "/admin/")):
            return r.continue_()
        if path in {"/auth/session", "/auth/me"}:
            data = {
                "id": 1,
                "email": "review@test.dev",
                "role": "admin",
                "is_active": True,
            }
        elif path == "/api/homepage":
            data = state["home"]
        elif path == "/admin/content/901":
            if r.request.method == "PATCH":
                payload = r.request.post_data_json
                assert payload["expected_updated_at"] == state["home"]["updated_at"]
                state["home"].update(payload)
            data = state["home"]
        elif path == "/api/catalog":
            data = {"revision": "feedback-fixture"}
        elif path == "/api/me/notifications":
            data = {"unread": 0, "items": []}
        elif path == "/api/video":
            number = int(parse_qs(urlsplit(r.request.url).query).get("page", [1])[0])
            data = {
                "items": [],
                "total": 180,
                "page": number,
                "page_size": 60,
                "pages": 3,
            }
        else:
            data = {
                "items": [state["home"]] if path == "/admin/content" else [],
                "total": 1,
                "page": 1,
                "page_size": 20,
                "pages": 1,
            }
        r.fulfill(json=data)

    ctx.route("**/*", route)
    ctx.route_web_socket("**/*", lambda ws: None)

    def edit(part):
        page.goto(base + "/cms?tab=" + part, wait_until="networkidle")
        page.locator(".cms-card .cms-pill--active").click()
        return page.get_by_role("dialog")

    def save(dialog):
        dialog.get_by_role("button", name="Lưu", exact=True).click()
        expect(dialog).to_have_count(0)

    try:
        dialog = edit("intro")
        dialog.locator("textarea").first.fill("Only community intro changed")
        save(dialog)
        assert state["home"]["body"]["support"] == home["body"]["support"]
        assert state["home"]["body"]["product"] == home["body"]["product"]
        assert state["home"]["body"]["leader"] is None
        assert state["home"]["body"]["sections"] == home["body"]["sections"]
        assert [m["media_id"] for m in state["home"]["media"]] == [901, 902, 903]
        passed(
            "Editing community intro preserves legacy funds, products "
            "and all attached media"
        )

        dialog = edit("products")
        dialog.get_by_label("Tên sản phẩm", exact=True).fill("Updated product")
        dialog.get_by_role("button", name="Gỡ ảnh", exact=True).click()
        save(dialog)
        assert "media_id" not in state["home"]["body"]["product"]
        assert state["home"]["body"]["product"]["extra"] == "Keep product extra"
        assert state["home"]["body"]["support"] == home["body"]["support"]
        assert [m["media_id"] for m in state["home"]["media"]] == [901, 903]
        passed(
            "Product-only edits retain fund data and QR/hero "
            "while removing its own image"
        )

        before = copy.deepcopy(state["home"]["body"])
        dialog = edit("support")
        expect(dialog.get_by_label("Mục đích sử dụng", exact=False)).to_have_value(
            home["body"]["support"]["used"]
        )
        dialog.get_by_label("Đã sử dụng (VNĐ)", exact=True).fill("1.000.000")
        dialog.get_by_label("Mục đích sử dụng", exact=False).fill(
            "Hosting & domain\nCommunity fixtures"
        )
        save(dialog)
        body = state["home"]["body"]
        assert "used" not in body["support"]
        assert body["support"]["used_amount"] == "1.000.000"
        assert body["support"]["purposes"] == ["Hosting & domain", "Community fixtures"]
        assert body["support"]["extra"] == "Keep fund extra"
        assert {k: v for k, v in body.items() if k != "support"} == {
            k: v for k, v in before.items() if k != "support"
        }
        page.goto(base + "/community?tab=support", wait_until="networkidle")
        expect(page.locator(".community__purposes li")).to_have_text(
            ["Hosting & domain", "Community fixtures"]
        )
        expect(page.locator(".community__info")).to_contain_text("1.000.000 VNĐ")
        passed(
            "Legacy fund text migrates only in its own form "
            "and renders amount/list without escaping ampersands"
        )

        page.goto(base + "/video/all?q=review&page=2#keep", wait_until="networkidle")
        assert page.url == base + "/video?q=review&page=2#keep"
        expect(page.get_by_placeholder("Tìm kiếm video")).to_have_value("review")
        passed("Legacy video URLs retain search, pagination and hash after redirect")

        state["home"]["media"] = [
            {
                "media_id": 999,
                "url": "/missing-hero.png",
                "mime_type": "image/png",
                "is_primary": True,
            }
        ]
        page.goto(base + "/", wait_until="networkidle")
        expect(page.locator(".home__hero-bg")).to_have_attribute(
            "src", re.compile(r"/assets/home-hero-.*\.webp$")
        )
        assert page.locator(".home__hero-bg").evaluate(
            "image => image.complete && image.naturalWidth > 0"
        )
        passed("A missing uploaded hero falls back to the bundled background")
        assert not errors, errors
    finally:
        ctx.close()
