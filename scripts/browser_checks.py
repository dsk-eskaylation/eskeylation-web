"""Browser regressions on a disposable localhost database and generated media.

Run after building frontend/dist. DATABASE_URL must explicitly name a local test DB.
No Drive, Supabase Storage or production credentials are used by this script.
"""

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
import wave
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8766"
EVIDENCE = ROOT / ".local" / "browser-checks"


def environment() -> dict[str, str]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "Browser checks require an explicit localhost test DATABASE_URL"
        )
    url = make_url(database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not any(
        marker in (url.database or "").lower() for marker in ("test", "audit")
    ):
        raise SystemExit(
            "Browser checks require an explicit localhost test DATABASE_URL"
        )
    return {
        **os.environ,
        "ENVIRONMENT": "dev",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "STORAGE_BACKEND": "local",
        "MEDIA_ROOT": str(EVIDENCE / "media"),
        "PUBLIC_CONTENT_SOURCE": "database",
        "SUPABASE_URL": "",
        "SUPABASE_SERVICE_KEY": "",
        "GOOGLE_DRIVE_API_KEY": "",
        "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE": "",
        "CORS_ORIGINS": json.dumps([BASE]),
    }


async def seed(password: str, tag: str) -> None:
    # Imported only after the isolation guard and environment overrides.
    from app.db import SessionLocal, engine
    from app.models.content import Content
    from app.models.enums import ContentStatus, ContentType, UserRole
    from app.models.media import ContentMedia, Media
    from app.models.user import User
    from app.services.security import hash_password

    media_dir = EVIDENCE / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), "orange").save(media_dir / "ui-image.png")
    with wave.open(str(media_dir / "ui-tone.wav"), "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\x00\x00" * (8000 * 30))
    async with SessionLocal() as session:
        users = {}
        for role in UserRole:
            user = User(
                email=f"browser-{role.value}-{tag}@test.dev",
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
            )
            session.add(user)
            users[role.value] = user
        await session.flush()
        image = Media(
            storage_key="ui-image.png",
            mime_type="image/png",
            size=(media_dir / "ui-image.png").stat().st_size,
            width=1200,
            height=800,
        )
        session.add(image)
        await session.flush()
        for i in range(55):
            session.add(
                Content(
                    type=ContentType.music,
                    status=ContentStatus.draft,
                    title=f"Browser draft {tag} {i:02d}",
                    slug=f"draft-{tag}-{i}",
                    body={"artist": "Browser artist"},
                    author_id=users["author"].id,
                )
            )
        for i in range(24):
            session.add(
                Content(
                    type=ContentType.music,
                    status=ContentStatus.published,
                    title=f"Điều bình thường {i:02d}",
                    slug=f"music-{tag}-{i}",
                    body={
                        "artist": "Browser artist",
                        "audio_url": f"/media/ui-tone.wav?track={i}",
                    },
                    author_id=users["admin"].id,
                    published_at=datetime.now(UTC),
                )
            )
        for kind in [ContentType.community, ContentType.gallery, ContentType.video]:
            for i in range(6 if kind == ContentType.community else 1):
                content = Content(
                    type=kind,
                    status=ContentStatus.published,
                    title=f"Browser {kind.value} {i}",
                    slug=f"{kind.value}-{tag}-{i}",
                    summary="Local browser test",
                    body={},
                    author_id=users["admin"].id,
                    published_at=datetime.now(UTC),
                )
                session.add(content)
                await session.flush()
                session.add(
                    ContentMedia(
                        content_id=content.id,
                        media_id=image.id,
                        position=0,
                        is_primary=True,
                    )
                )
        await session.commit()
    await engine.dispose()


def check_ui(password: str, tag: str) -> None:
    checks = []

    def passed(name):
        checks.append(name)
        print("PASS", name, flush=True)

    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--mute-audio"]}
        if os.environ.get("UI_BROWSER_EXECUTABLE"):
            options["executable_path"] = os.environ["UI_BROWSER_EXECUTABLE"]
        browser = playwright.chromium.launch(**options)

        def context(width=1440):
            ctx = browser.new_context(viewport={"width": width, "height": 900})
            # Font services are not part of these deterministic regression checks.
            ctx.route(
                "https://fonts.googleapis.com/**",
                lambda route: route.fulfill(content_type="text/css", body=""),
            )
            return ctx

        def login(page, role):
            page.goto(BASE + "/login", wait_until="networkidle")
            page.get_by_label("Email", exact=True).fill(
                f"browser-{role}-{tag}@test.dev"
            )
            page.get_by_label("Mật khẩu", exact=True).fill(password)
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            page.wait_for_url("**/community" if role == "member" else "**/cms")
            page.wait_for_load_state("networkidle")

        page = None
        try:
            for width in [390, 768, 1440]:
                ctx = context(width)
                page = ctx.new_page()
                page.goto(BASE + "/community", wait_until="networkidle")
                cell = page.locator(".cpost__cell").nth(4)
                cell.scroll_into_view_if_needed()
                before = page.evaluate("window.scrollY")
                cell.click()
                expect(page.get_by_role("dialog")).to_be_visible()
                bounds = page.get_by_role("dialog").bounding_box()
                assert abs(bounds["y"]) <= 1 and bounds["height"] <= 901
                assert abs(page.evaluate("window.scrollY") - before) <= 2
                page.keyboard.press("Escape")
                expect(page.get_by_role("dialog")).to_have_count(0)
                assert abs(page.evaluate("window.scrollY") - before) <= 2
                assert cell.evaluate("e=>document.activeElement===e")
                page.get_by_role("button", name="Tài khoản", exact=True).click()
                expect(
                    page.get_by_role("menuitem", name="Đăng nhập", exact=True)
                ).to_be_visible()
                assert page.locator(".layout__nav").bounding_box()["y"] == 0
                page.goto(BASE + "/", wait_until="networkidle")
                assert "Maintain" not in page.locator("body").inner_text()
                passed(f"{width}px pinned header, modal without scroll jump, homepage")
                ctx.close()

            ctx = context()
            page = ctx.new_page()
            page.goto(BASE + "/music", wait_until="networkidle")
            assert page.locator(".music__cat").count() == 0
            assert page.locator(".music__row").count() == 24
            search = page.get_by_role("searchbox")
            search.fill("no matching song 98765")
            expect(page.get_by_role("status")).to_contain_text("Không tìm thấy")
            expect(search).to_be_visible()
            search.fill("dieu binh thuong")
            assert page.locator(".music__row").count() == 24
            page.locator(".music__row").first.click()
            page.wait_for_function("()=>document.querySelector('audio').currentTime>.2")
            page.get_by_role("button", name="Tạm dừng", exact=True).click()
            assert page.locator("audio").evaluate("a=>a.paused")
            page.get_by_role("button", name="Phát", exact=True).click()
            page.get_by_role("slider", name="Tua bài hát").fill("10")
            page.wait_for_function("()=>document.querySelector('audio').currentTime>=9")
            page.get_by_role("button", name="Bài sau", exact=True).click()
            page.wait_for_function("()=>document.querySelector('audio').currentTime>.2")
            page.get_by_role("link", name="Ảnh", exact=True).click()
            assert not page.locator("audio").evaluate("a=>a.paused")
            passed(
                "Music search/empty state, play/pause/seek/next, background playback"
            )
            ctx.close()

            ctx = context()
            page = ctx.new_page()
            attempts = 0

            def temporary_outage(route):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    route.fulfill(status=503, body="Temporary test outage")
                else:
                    route.continue_()

            page.route("**/media/ui-tone.wav?*", temporary_outage)
            page.goto(BASE + "/music", wait_until="networkidle")
            page.locator(".music__row").first.click()
            expect(page.locator(".player-bar__status")).to_be_visible()
            page.get_by_role("button", name="Phát", exact=True).click()
            page.wait_for_function("()=>document.querySelector('audio').currentTime>.2")
            assert attempts <= 5, "Media retry must not loop requests"
            passed("Temporary media 503: visible error, manual retry, bounded requests")
            ctx.close()

            ctx = context()
            page = ctx.new_page()
            login(page, "admin")
            pager = page.get_by_role("navigation", name="Phân trang nội dung")
            pager.get_by_role("button", name="Trang sau").click()
            expect(pager).to_contain_text("Trang 2/")
            page.locator(".cms__filters").get_by_role(
                "button", name="Nhạc", exact=True
            ).click()
            expect(pager).to_contain_text("Trang 1/")
            page.get_by_role("button", name="+ Nội dung mới", exact=True).click()
            dialog = page.get_by_role("dialog")
            title = "Browser created " + tag
            dialog.get_by_label("Tiêu đề", exact=True).fill(title)
            dialog.get_by_label("Nghệ sĩ", exact=True).fill("Browser artist")
            dialog.get_by_role("button", name="Lưu", exact=True).click()
            expect(dialog).to_have_count(0)
            row = page.locator(".cms__row").filter(has_text=title)
            row.get_by_role("button", name="Đăng", exact=True).click()
            expect(row).to_contain_text("Đã đăng")
            row.get_by_role("button", name="Gỡ", exact=True).click()
            expect(row).to_contain_text("Nháp")
            row.get_by_role("button", name="Xoá", exact=True).click()
            dialog.get_by_role("button", name="Xoá vĩnh viễn", exact=True).click()
            expect(row).to_have_count(0)
            page.get_by_role("button", name="Tổng quan", exact=True).click()
            expect(page.locator(".dash")).to_be_visible()
            page.get_by_role("button", name="Kiểm duyệt", exact=True).click()
            expect(
                page.get_by_role("navigation", name="Phân trang chờ duyệt")
            ).to_be_visible()
            page.get_by_role("button", name="Tài khoản", exact=True).click()
            expect(
                page.get_by_role("button", name="+ Thêm tài khoản", exact=True)
            ).to_be_visible()
            passed(
                "Admin pagination/filter reset, create/publish/unpublish/delete, "
                "dashboard/moderation/users"
            )
            ctx.close()
            member_context = context()
            member_page = member_context.new_page()
            page = member_page
            login(member_page, "member")
            post = member_page.locator(".cpost").first
            post.get_by_role("button", name="Bình luận", exact=True).click()
            draft = post.get_by_placeholder("Viết bình luận...")
            draft.fill("Browser comment " + tag)
            post.get_by_role("button", name="Gửi", exact=True).click()
            comment = post.locator(".cpost__comment")
            expect(comment).to_have_count(1)
            expect(
                post.get_by_role("button", name="1 bình luận", exact=True)
            ).to_be_visible()
            comment.get_by_role("button", name="Sửa", exact=True).click()
            comment.locator("input").fill("Edited browser comment " + tag)
            comment.get_by_role("button", name="Lưu", exact=True).click()
            expect(comment).to_contain_text("Edited browser comment " + tag)
            admin_context = context()
            admin_page = admin_context.new_page()
            login(admin_page, "admin")
            post_id = member_page.request.get(
                BASE + "/api/community?page_size=1"
            ).json()["items"][0]["id"]
            comment_id = member_page.request.get(
                BASE + f"/api/community/{post_id}/comments"
            ).json()["items"][0]["id"]
            csrf = next(
                cookie["value"]
                for cookie in admin_context.cookies()
                if cookie["name"] == "esk_csrf"
            )
            response = admin_page.request.delete(
                BASE + f"/admin/moderation/comments/{comment_id}",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status == 204
            expect(comment).to_have_count(0)
            expect(post.locator(".cpost__stats-comments")).to_have_count(0)
            passed(
                "Comment POST/socket deduplication, own edit, "
                "admin delete updates live thread"
            )
            admin_context.close()
            member_context.close()
            for role in ["author", "editor", "member"]:
                ctx = context()
                page = ctx.new_page()
                login(page, role)
                if role == "member":
                    page.goto(BASE + "/cms")
                    page.wait_for_url("**/community")
                else:
                    expect(
                        page.get_by_role("button", name="Tài khoản", exact=True)
                    ).to_have_count(0)
                    if role == "author":
                        expect(
                            page.get_by_role("button", name="Đăng", exact=True)
                        ).to_have_count(0)
                        expect(
                            page.get_by_role("button", name="Xoá", exact=True)
                        ).to_have_count(0)
                passed(f"{role} UI permission boundary")
                ctx.close()
        except BaseException:
            if page is not None and not page.is_closed():
                page.screenshot(path=str(EVIDENCE / "failure.png"))
            raise
        finally:
            browser.close()
    (EVIDENCE / "results.json").write_text(
        json.dumps(checks, indent=2), encoding="utf-8"
    )


def main() -> None:
    os.environ.update(environment())
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend before browser checks")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True
    )
    tag, password = uuid.uuid4().hex[:10], secrets.token_urlsafe(24)
    asyncio.run(seed(password, tag))
    with (EVIDENCE / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8766",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1) as client:
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError(
                            "Browser test server exited; inspect server.log"
                        )
                    try:
                        if client.get(BASE + "/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Browser test server did not start")
            check_ui(password, tag)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
