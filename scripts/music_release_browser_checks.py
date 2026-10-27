"""Music release regressions with disposable API fixtures and local accounts."""

from playwright.sync_api import expect


def check_music_release(base, context, login, passed):
    ctx = context()
    page = ctx.new_page()
    album = {
        "slug": "release-fixture",
        "title": "Album kiểm thử",
        "kind": "album",
        "year": 2026,
        "cover_url": None,
        "description": None,
        "track_count": 1,
    }
    mode = {"album_error": True, "embeds": False, "mixed": False}
    try:
        page.goto(base + "/music", wait_until="networkidle")
        page.get_by_role("searchbox").fill("Browser artist")
        assert page.locator(".music__row").count() > 0
        expect(page.get_by_role("combobox", name="Lọc theo thể loại")).to_have_count(0)
        passed("Music search still matches artists; genre control stays removed")
        tracks = page.request.get(base + "/api/music?page_size=60").json()["items"]
        assert tracks

        def albums(route):
            if mode["album_error"]:
                route.fulfill(status=503, json={"detail": "Fixture unavailable"})
            else:
                route.fulfill(json=[album])

        page.route(base + "/api/albums", albums)
        page.route(
            base + "/api/catalog",
            lambda route: route.fulfill(json={"revision": "music-release-fixture"}),
        )
        page.goto(base + "/music/all?view=albums", wait_until="networkidle")
        expect(page.get_by_role("alert")).to_contain_text("Chưa tải được album")
        expect(page.locator(".album-grid")).to_have_count(0)
        mode["album_error"] = False
        page.get_by_role("button", name="Thử lại", exact=True).click()
        expect(page.locator(".album-grid__card")).to_have_count(2)
        passed("Album API failure is visible and Retry recovers the grid")

        def library(route):
            embed = {
                **tracks[0],
                "id": 999999,
                "title": "Bài nhúng kiểm thử",
                "body": {"artist": "Browser artist"},
                "media": [],
                "player_url": "https://w.soundcloud.com/player/?url=https%3A%2F%2Fsoundcloud.com%2Fexample%2Fexample",
            }
            items = [tracks[0], embed] if mode["mixed"] else [embed]
            route.fulfill(
                json={
                    "items": items,
                    "total": len(items),
                    "page": 1,
                    "page_size": 60,
                    "pages": 1,
                }
            )

        page.route(base + "/api/music?*", library)
        page.route(
            "https://w.soundcloud.com/**",
            lambda route: route.fulfill(
                body="<p>Fixture player</p>", content_type="text/html"
            ),
        )
        page.goto(base + "/music", wait_until="networkidle")
        page.get_by_role("button", name="Phát bài nhúng đầu tiên theo thứ tự A-Z", exact=True).click()
        expect(page.locator(".embed-dock iframe")).to_be_visible()
        page.get_by_role("button", name="Đóng trình phát", exact=True).click()
        page.get_by_role("button", name="Phát bài nhúng ngẫu nhiên", exact=True).click()
        expect(page.locator(".embed-dock iframe")).to_be_visible()
        passed("Embedded-only library can play the first or a random track")

        mode["mixed"] = True
        page.goto(base + "/music", wait_until="networkidle")
        expect(page.locator(".music__hint").last).to_contain_text(
            "1 bài có file âm thanh"
        )
        page.get_by_role("button", name="Phát danh sách audio theo thứ tự A-Z", exact=True).click()
        page.wait_for_function("()=>document.querySelector('audio').currentTime > .1")
        expect(page.locator(".embed-dock")).to_have_count(0)
        page.get_by_role("button", name="Phát Bài nhúng kiểm thử", exact=True).click()
        expect(page.locator(".embed-dock iframe")).to_be_visible()
        assert page.locator("audio").evaluate("e=>e.paused")
        passed(
            "Mixed sources explain audio scope and never play audio and embed together"
        )

        # Use the publisher account here so this extra regression group does not
        # consume the admin account's five-login window used by the other groups.
        login(page, "editor")
        trigger = page.locator(".cms-menu > button").first
        trigger.focus()
        page.keyboard.press("ArrowUp")
        items = page.get_by_role("menuitem")
        expect(items.last).to_be_focused()
        page.keyboard.press("Home")
        expect(items.first).to_be_focused()
        page.keyboard.press("ArrowDown")
        expect(items.nth(1)).to_be_focused()
        page.keyboard.press("End")
        expect(items.last).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.get_by_role("menu")).to_have_count(0)
        expect(trigger).to_be_focused()
        passed("CMS row menu supports arrows, Home/End, Escape and focus restoration")
    finally:
        ctx.close()
