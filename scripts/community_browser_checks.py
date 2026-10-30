"""Member posting, post dialog, inline comment delete and notifications."""

import io

from PIL import Image
from playwright.sync_api import expect


def _png(color):
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="PNG")
    return buf.getvalue()


def _csrf(ctx):
    return next(c["value"] for c in ctx.cookies() if c["name"] == "esk_csrf")


def check_member_posting(base, context, login, passed):
    native_dialogs = []
    member_ctx = context()
    page = member_ctx.new_page()
    page.on(
        "dialog",
        lambda dialog: (native_dialogs.append(dialog.message), dialog.dismiss()),
    )
    admin_ctx = context()
    admin = admin_ctx.new_page()
    try:
        login(admin, "admin", account="moderator")
        login(page, "member", account="poster")
        composer = page.get_by_role("dialog", name="Tạo bài viết")
        prompt = page.get_by_role("button", name="Bạn đang nghĩ gì về ESKAYLATION?")

        prompt.click()
        expect(composer).to_be_visible()
        expect(composer.get_by_label("Nội dung bài viết")).to_be_focused()
        composer.get_by_label("Nội dung bài viết").fill("Bản nháp sẽ bỏ")
        composer.get_by_role("button", name="Huỷ", exact=True).click()
        expect(composer).to_have_count(0)
        prompt.click()
        expect(composer.get_by_label("Nội dung bài viết")).to_have_value("")
        page.keyboard.press("Escape")
        expect(composer).to_have_count(0)
        passed("Composer cancel and Escape close at once without a browser dialog")

        prompt.click()
        post_button = composer.get_by_role("button", name="Đăng", exact=True)
        expect(post_button).to_be_disabled()
        composer.locator("input[type=file]").set_input_files(
            [
                {
                    "name": "red.png",
                    "mimeType": "image/png",
                    "buffer": _png((180, 40, 40)),
                },
                {
                    "name": "blue.png",
                    "mimeType": "image/png",
                    "buffer": _png((40, 40, 180)),
                },
                {
                    "name": "note.txt",
                    "mimeType": "text/plain",
                    "buffer": b"not an image",
                },
            ]
        )
        expect(composer.get_by_role("alert")).to_contain_text("Chỉ hỗ trợ ảnh")
        expect(composer.locator(".composer__image--done")).to_have_count(2)
        composer.get_by_role("button", name="Gỡ ảnh blue.png").click()
        expect(composer.locator(".composer__image")).to_have_count(1)
        expect(post_button).to_be_disabled()
        composer.get_by_label("Nội dung bài viết").fill("Ảnh buổi offline\nVui quá")
        expect(post_button).to_be_enabled()
        post_button.click()
        expect(composer).to_have_count(0)
        expect(page.get_by_text("Bài sẽ hiển thị sau khi admin duyệt")).to_be_visible()
        mine = page.request.get(base + "/api/me/posts").json()["items"]
        post = next(p for p in mine if p["title"] == "Ảnh buổi offline")
        assert post["body"]["review_status"] == "draft" and len(post["media"]) == 1
        passed("Member post with photo: picker, type check, remove, submit for review")

        published = admin.request.post(
            base + f"/admin/content/{post['id']}/publish",
            headers={"X-CSRF-Token": _csrf(admin_ctx)},
        )
        assert published.status == 200, published.text()
        page.goto(base + "/community", wait_until="networkidle")
        card = page.locator(".cpost").filter(has_text="Ảnh buổi offline").first
        card.locator(".cpost__cell").first.click()
        detail = page.locator(".cpost--detail")
        expect(detail.locator(".cpost__visual img")).to_be_visible()
        assert f"post={post['slug']}" in page.url
        detail.get_by_placeholder("Viết bình luận...").fill("Bình luận sẽ xoá")
        detail.get_by_role("button", name="Gửi", exact=True).click()
        comment = detail.locator(".cpost__comment").filter(has_text="Bình luận sẽ xoá")
        expect(comment).to_have_count(1)
        comment.get_by_role("button", name="Xoá", exact=True).click()
        expect(comment.get_by_text("Xoá bình luận này?")).to_be_visible()
        comment.get_by_role("button", name="Huỷ", exact=True).click()
        expect(comment).to_have_count(1)
        comment.get_by_role("button", name="Xoá", exact=True).click()
        comment.get_by_role("button", name="Xoá", exact=True).click()
        expect(comment).to_have_count(0)
        passed("Post dialog opens from the feed; comment delete confirms inline")

        reacted = admin.request.put(
            base + f"/api/community/{post['id']}/reaction",
            data={"type": "love"},
            headers={"X-CSRF-Token": _csrf(admin_ctx)},
        )
        assert reacted.status == 200, reacted.text()
        page.goto(base + "/profile", wait_until="networkidle")
        bell = page.get_by_role("button", name="Thông báo, 1 chưa đọc")
        expect(bell).to_be_visible()
        bell.click()
        expect(page.get_by_text("đã bày tỏ cảm xúc về bài viết")).to_be_visible()
        expect(page.get_by_role("button", name="Thông báo", exact=True)).to_be_visible()
        expect(
            page.get_by_role("button", name="Mở bài Ảnh buổi offline")
        ).to_be_visible()
        passed("Reaction notification badge, panel and profile post grid")
        assert native_dialogs == [], f"Unexpected browser dialogs: {native_dialogs}"
    finally:
        member_ctx.close()
        admin_ctx.close()
