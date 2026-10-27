"""Browser regressions for failures and larger conversations, on fake local data."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import expect


def check_review_fixes(base, context_factory, login, passed, evidence):
    assert base.startswith("http://127.0.0.1:"), "Local fake data only"
    ctx = context_factory()
    page = ctx.new_page()
    login(page, "admin")
    csrf = next(c["value"] for c in ctx.cookies() if c["name"] == "esk_csrf")
    headers = {"X-CSRF-Token": csrf}
    created = []

    def request(method, path, data=None, status=200):
        response = ctx.request.fetch(
            base + path, method=method, data=data, headers=headers
        )
        assert response.status == status, (path, response.status)
        return response.json() if status != 204 else None

    try:
        page.route(
            "**/auth/logout",
            lambda route: route.fulfill(status=503, json={"detail": "Fake outage"}),
        )
        page.get_by_role("button", name="Đăng xuất", exact=True).click()
        expect(
            page.get_by_text("Chưa đăng xuất được. Vui lòng thử lại.", exact=True)
        ).to_be_visible()
        assert "/cms" in page.url
        assert ctx.request.get(base + "/auth/me").status == 200
        page.unroute("**/auth/logout")
        page.get_by_role("button", name="Đăng xuất", exact=True).click()
        page.wait_for_url("**/login")
        assert ctx.request.get(base + "/auth/me").status == 401
        passed("Failed logout preserves session; retry revokes it")
        login(page, "admin")
        csrf = next(c["value"] for c in ctx.cookies() if c["name"] == "esk_csrf")
        headers = {"X-CSRF-Token": csrf}
        original = request(
            "POST",
            "/admin/content",
            {
                "type": "community",
                "title": "Fake concurrent review",
                "summary": "Fake original",
            },
            201,
        )
        created.append(original["id"])
        page.goto(base + "/cms?type=community", wait_until="networkidle")
        page.locator(".cms-table tbody tr").filter(
            has=page.get_by_text(original["title"], exact=True)
        ).get_by_role("button", name="Sửa", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Tiêu đề", exact=True).fill("My unsaved changes")
        request(
            "PATCH",
            f"/admin/content/{original['id']}",
            {
                "title": "Other editor saved",
                "expected_updated_at": original["updated_at"],
            },
        )
        with page.expect_response(
            lambda r: r.request.method == "PATCH" and "/admin/content/" in r.url
        ) as response:
            dialog.get_by_role("button", name="Lưu", exact=True).click()
        assert response.value.status == 409
        expect(dialog.get_by_label("Tiêu đề", exact=True)).to_have_value(
            "My unsaved changes"
        )
        expect(dialog.get_by_role("alert")).to_contain_text("Bài đã được cập nhật")
        passed("Stale CMS edits return 409 and preserve the unsaved form")
        ctx.close()

        ctx = context_factory()
        page = ctx.new_page()
        login(page, "admin")
        csrf = next(c["value"] for c in ctx.cookies() if c["name"] == "esk_csrf")
        headers = {"X-CSRF-Token": csrf}
        post = request(
            "POST",
            "/admin/content",
            {
                "type": "community",
                "title": "Fake large conversation",
                "summary": "Only fake comments",
            },
            201,
        )
        created.append(post["id"])
        request("POST", f"/admin/content/{post['id']}/publish")
        user = request("GET", "/auth/me")

        async def seed_comments():
            from app.db import SessionLocal, engine
            from app.models.community import Comment

            async with SessionLocal() as session:
                session.add_all(
                    [
                        Comment(
                            content_id=post["id"],
                            user_id=user["id"],
                            body=f"Fake review comment {n}",
                        )
                        for n in range(55)
                    ]
                )
                await session.commit()
            await engine.dispose()

        # Playwright's sync API owns this thread's loop; seed in a separate one.
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, seed_comments()).result(timeout=15)
        page.goto(base + "/community", wait_until="networkidle")
        article = page.locator(".cpost").filter(
            has=page.get_by_text(post["title"], exact=True)
        )
        article.get_by_role("button", name="55 bình luận", exact=True).click()
        article = page.locator(".cpost--detail")
        expect(article.locator(".cpost__comment")).to_have_count(50)
        request(
            "POST",
            f"/api/community/{post['id']}/comments",
            {"body": "Fake socket comment while paging"},
            201,
        )
        expect(article.locator(".cpost__comment")).to_have_count(51)
        article.get_by_role("button", name="Xem thêm bình luận", exact=True).click()
        expect(article.locator(".cpost__comment")).to_have_count(56)
        expect(
            article.get_by_text("Fake socket comment while paging", exact=True)
        ).to_have_count(1)
        expect(
            article.get_by_role("button", name="Xem thêm bình luận", exact=True)
        ).to_have_count(0)
        page.screenshot(path=str(evidence / "comments-over-50.png"))
        passed("Cursor paging loads 55 comments and a concurrent socket comment once")
    finally:
        for content_id in created:
            ctx.request.delete(base + f"/admin/content/{content_id}", headers=headers)
        ctx.close()

    ctx = context_factory()
    page = ctx.new_page()
    page.route("**/assets/Music-*.js", lambda route: route.abort("failed"))
    page.goto(base + "/music", wait_until="networkidle")
    expect(
        page.get_by_role("heading", name="Chưa tải được trang", exact=True)
    ).to_be_visible()
    page.screenshot(path=str(evidence / "chunk-recovery.png"))
    page.unroute("**/assets/Music-*.js")
    page.get_by_role("button", name="Tải lại trang", exact=True).click()
    expect(
        page.get_by_role("heading", name="Thư viện âm nhạc", exact=True)
    ).to_be_visible()
    passed("Lazy chunk failure offers accessible recovery; reload works")
    ctx.close()

    ctx = context_factory()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(
        "**/api/homepage",
        lambda route: route.fulfill(
            json={
                "id": 0,
                "type": "homepage",
                "title": "Legacy",
                "slug": "legacy",
                "summary": None,
                "published_at": None,
                "body": {"maintain": [{"text": "invalid"}, "Valid legacy line"]},
                "media": [],
            }
        ),
    )
    page.goto(base, wait_until="networkidle")
    expect(page.get_by_role("heading", name="ESKAYLATION", exact=True)).to_be_visible()
    expect(page.get_by_text("Valid legacy line", exact=True)).to_be_visible()
    assert not errors, errors
    passed("Legacy malformed support entries cannot crash the homepage")
    ctx.close()
