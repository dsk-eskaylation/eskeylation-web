"""Design regressions: only disposable local accounts, content and API fixtures."""

from contextlib import suppress
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Error, expect


def library_fixture(case, payload):
    def handle(route):
        if case["state"] == "loading":
            case["pending"].append(route)
        elif case["state"] == "error":
            route.fulfill(status=503, json={"detail": "Fake unavailable"})
        else:
            query = parse_qs(urlparse(route.request.url).query)
            number = int(query.get("page", ["1"])[0])
            searching = bool(query.get("q"))
            route.fulfill(
                json={
                    **payload,
                    "items": []
                    if searching
                    else [
                        {
                            **payload["items"][0],
                            "id": 9000 + number,
                            "title": f"Fake page {number}",
                        }
                    ],
                    "page": number,
                    "pages": 0 if searching else 2,
                    "total": 0 if searching else 61,
                }
            )

    return handle


def check_design_flows(base, context, login, passed, evidence):
    ctx = context()
    page = ctx.new_page()
    try:
        login(page, "admin")
        for width in [320, 390, 768, 1440]:
            page.set_viewport_size({"width": width, "height": 900})
            expect(
                page.get_by_role("button", name="Tài khoản", exact=True)
            ).to_be_visible()
            controls = page.locator(
                ".cms__topbar-actions button, .cms__topbar-actions a"
            )
            for control in controls.all():
                bounds = control.bounding_box()
                assert (
                    bounds
                    and bounds["x"] >= 0
                    and bounds["x"] + bounds["width"] <= width
                )
            page.screenshot(path=str(evidence / f"cms-fixed-{width}.png"))
        passed("CMS navigation stays reachable at 320/390/768/1440px")
        page.get_by_role("button", name="Kiểm duyệt", exact=True).click()
        assert parse_qs(urlparse(page.url).query)["tab"] == ["moderation"]
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("heading", level=1)).to_have_text("Kiểm duyệt")
        page.get_by_role("button", name="Nội dung", exact=True).click()
        page.locator(".cms__filters").get_by_role(
            "button", name="Nhạc", exact=True
        ).click()
        page.locator(".cms__filters").get_by_role(
            "button", name="Nháp", exact=True
        ).click()
        page.reload(wait_until="networkidle")
        params = parse_qs(urlparse(page.url).query)
        assert params["type"] == ["music"] and params["status"] == ["draft"]
        expect(page.locator(".cms__row").first).to_be_visible()
        passed("CMS tab and content filters survive reload through URL state")

        page.get_by_role("button", name="+ Nội dung mới", exact=True).click()
        title = page.get_by_role("dialog").get_by_label("Tên bài hát", exact=True)
        title.fill("Bản nháp giả chưa lưu")
        # A dismissed reload warning leaves the draft intact.
        dialogs = []

        def cancel_reload(dialog):
            dialogs.append(dialog.type)
            dialog.dismiss()

        page.on("dialog", cancel_reload)
        with suppress(Error):
            page.reload(timeout=5000)
        page.remove_listener("dialog", cancel_reload)
        assert "beforeunload" in dialogs
        expect(title).to_have_value("Bản nháp giả chưa lưu")
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog", name="Thay đổi chưa lưu")).to_be_visible()
        expect(
            page.get_by_role("button", name="Tiếp tục chỉnh sửa", exact=True)
        ).to_be_focused()
        page.get_by_role("button", name="Tiếp tục chỉnh sửa", exact=True).click()
        expect(title).to_have_value("Bản nháp giả chưa lưu")
        page.get_by_role("button", name="Huỷ", exact=True).click()
        expect(page.get_by_role("dialog", name="Thay đổi chưa lưu")).to_be_visible()
        page.keyboard.press("Escape")
        expect(title).to_have_value("Bản nháp giả chưa lưu")
        page.get_by_role("dialog").click(position={"x": 3, "y": 3})
        expect(page.get_by_role("dialog", name="Thay đổi chưa lưu")).to_be_visible()
        page.get_by_role("button", name="Bỏ thay đổi", exact=True).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        passed(
            "Dirty CMS drafts survive Escape/cancel/backdrop/reload "
            "unless discard is confirmed"
        )

        page.get_by_role("button", name="Tài khoản", exact=True).click()
        page.get_by_role("button", name="Thêm tài khoản", exact=False).click()
        page.get_by_role("dialog").get_by_label("Email", exact=True).fill(
            "fake-unsaved@test.dev"
        )
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog", name="Thay đổi chưa lưu")).to_be_visible()
        page.get_by_role("button", name="Bỏ thay đổi", exact=True).click()
        passed("New-account form uses the same unsaved-change protection")

        def homepage(route):
            route.fulfill(
                json={
                    "id": -1,
                    "title": "Fake homepage",
                    "media": [],
                    "body": {
                        "credits": [
                            {
                                "role": "QA",
                                "names": ["Người Một", "Người Hai", "Người Ba"],
                            },
                            {"role": "Empty role", "names": []},
                        ]
                    },
                }
            )

        page.route("**/api/homepage", homepage)
        page.goto(base + "/", wait_until="networkidle")
        expect(page.get_by_text("Empty role", exact=True)).to_have_count(0)
        expect(page.get_by_text("Người Ba", exact=True)).to_be_hidden()
        toggle = page.get_by_role("button", name="Xem thêm", exact=True)
        toggle.click()
        expect(page.get_by_text("Người Ba", exact=True)).to_be_visible()
        toggle = page.get_by_role("button", name="Thu gọn", exact=True)
        expect(toggle).to_have_attribute("aria-expanded", "true")
        toggle.click()
        expect(page.get_by_text("Người Hai", exact=True)).to_be_hidden()
        page.unroute("**/api/homepage", homepage)
        passed("Credits expand all members and hide empty placeholder groups")

        page.goto(base + "/community", wait_until="networkidle")
        page.mouse.move(0, 0)
        reaction = page.locator(".cpost__react-wrap").first
        reaction.locator("button").first.focus()
        page.keyboard.press("ArrowDown")
        choices = reaction.locator(".cpost__picker-item")
        expect(choices.first).to_be_focused()
        page.keyboard.press("ArrowRight")
        expect(choices.nth(1)).to_be_focused()
        page.keyboard.press("Escape")
        expect(choices).to_have_count(0)
        trigger = reaction.get_by_role("button", name="Chọn cảm xúc", exact=True)
        expect(trigger).to_be_focused()
        page.keyboard.press("Enter")
        expect(choices.first).to_be_focused()
        selected = choices.nth(1).get_attribute("aria-label")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Enter")
        expect(reaction.locator("button").first).to_contain_text(selected)
        passed("Reaction picker supports keyboard open, arrows, Escape and selection")

        for route_name, kind, noun in [
            ("/music/all", "music", "bài hát"),
            ("/video/all", "video", "video"),
        ]:
            payload = page.request.get(base + f"/api/{kind}?page_size=60").json()
            case = {"state": "loading", "pending": []}
            library = library_fixture(case, payload)
            pattern = f"**/api/{kind}?**"
            page.route(pattern, library)
            page.goto(base + route_name, wait_until="domcontentloaded")
            expect(page.get_by_text(f"Đang tải {noun}…", exact=True)).to_be_visible()
            case["state"] = "error"
            for request in case["pending"]:
                request.fulfill(status=503, json={"detail": "Fake unavailable"})
            expect(page.get_by_role("alert")).to_contain_text(f"Chưa tải được {noun}.")
            case["state"] = "success"
            page.get_by_role("button", name="Thử lại", exact=True).click()
            expect(page.get_by_text("Fake page 1", exact=False).first).to_be_visible()
            nav = page.get_by_role(
                "navigation",
                name=f"Phân trang {'nhạc' if kind == 'music' else 'video'}",
            )
            expect(nav).to_have_class("pagination")
            nav.get_by_role("button", name="Trang sau", exact=True).click()
            expect(
                nav.get_by_role("button", name="Trang 2", exact=True)
            ).to_have_attribute("aria-current", "page")
            assert parse_qs(urlparse(page.url).query)["page"] == ["2"]
            page.reload(wait_until="networkidle")
            expect(page.get_by_text("Fake page 2", exact=False).first).to_be_visible()
            page.go_back(wait_until="networkidle")
            expect(page.get_by_text("Fake page 1", exact=False).first).to_be_visible()
            search = page.get_by_role("searchbox")
            search.fill("Không có kết quả giả")
            expect(
                page.get_by_text(f"Không tìm thấy {noun} phù hợp.", exact=True)
            ).to_be_visible()
            assert "page" not in parse_qs(urlparse(page.url).query)
            page.get_by_role("button", name="Xóa tìm kiếm", exact=True).click()
            expect(page.get_by_text("Fake page 1", exact=False).first).to_be_visible()
            page.unroute(pattern, library)
            passed(
                f"{kind} grid: loading/error/retry, pagination, URL reload/back, search"
            )

        for route_name in [
            "/",
            "/music",
            "/music/all",
            "/video",
            "/video/all",
            "/photos",
            "/community",
            "/login",
            "/register",
            "/missing-design-page",
        ]:
            page.goto(base + route_name, wait_until="networkidle")
            expect(page.get_by_role("main")).to_have_count(1)
            expect(page.get_by_role("heading", level=1)).to_have_count(1)
        expect(
            page.get_by_role("heading", name="Không tìm thấy trang", exact=True)
        ).to_be_visible()
        page.get_by_role("link", name="Về trang chủ", exact=True).click()
        expect(page.get_by_role("heading", level=1)).to_have_text("ESKAYLATION")
        page.keyboard.press("Tab")
        passed("Public/auth main and h1; unknown routes offer a working return link")

        page.route(
            "**/auth/login",
            lambda route: route.fulfill(
                status=401, json={"detail": "Thông tin đăng nhập không đúng"}
            ),
        )
        page.goto(base + "/login", wait_until="networkidle")
        page.get_by_label("Email", exact=True).fill("fake-invalid@test.dev")
        page.get_by_label("Mật khẩu", exact=True).fill("fake-wrong-password")
        page.get_by_role("button", name="Đăng nhập", exact=True).click()
        expect(page.get_by_role("alert")).to_have_id("login-error")
        expect(page.get_by_label("Email", exact=True)).to_be_focused()
        expect(page.get_by_label("Email", exact=True)).to_have_attribute(
            "aria-describedby", "login-error"
        )
        page.unroute("**/auth/login")
        page.goto(base + "/register", wait_until="networkidle")
        page.get_by_label("Email", exact=True).fill("fake-register@test.dev")
        page.locator("#register-password").fill("fake-password-A")
        page.locator("#register-confirm").fill("fake-password-B")
        page.get_by_role("button", name="Đăng ký", exact=True).click()
        expect(page.locator("#register-confirm")).to_be_focused()
        expect(page.locator("#register-confirm")).to_have_attribute(
            "aria-invalid", "true"
        )
        expect(page.get_by_role("alert")).to_have_id("register-error")
        passed("Auth errors announce, associate fields and focus the correction target")
    except BaseException:
        page.screenshot(path=str(evidence / "design-failure.png"))
        raise
    finally:
        ctx.close()
