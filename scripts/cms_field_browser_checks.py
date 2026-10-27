"""Exercise content-specific forms and homepage avatars using fake local media."""

from playwright.sync_api import expect


def check_cms_fields(base, context_factory, login, passed, evidence):
    context = context_factory()
    admin = context.new_page()
    login(admin, "admin")
    csrf = next(c["value"] for c in context.cookies() if c["name"] == "esk_csrf")
    created = []
    uploads = set()
    errors = []
    admin.on("pageerror", lambda error: errors.append(str(error)))

    def api(method, path, data=None, status=200):
        response = admin.request.fetch(
            base + path, method=method, data=data, headers={"X-CSRF-Token": csrf}
        )
        assert response.status == status, (method, path, response.status)
        return response.json() if status != 204 else None

    def new(kind):
        admin.goto(base + "/cms?type=" + kind, wait_until="networkidle")
        admin.locator(".cms-top").get_by_role("button", name="+ Thêm").click()
        return admin.get_by_role("dialog")

    def save(dialog, creating=False):
        with admin.expect_response(
            lambda response: (
                response.request.method == ("POST" if creating else "PATCH")
                and "/admin/content" in response.url
            )
        ) as pending:
            dialog.get_by_role("button", name="Lưu", exact=True).click()
        assert pending.value.status == (201 if creating else 200)
        content = pending.value.json()
        if creating:
            created.append(content["id"])
        uploads.update(item["media_id"] for item in content["media"])
        expect(dialog).to_have_count(0)
        return content

    def edit(content):
        admin.goto(base + "/cms?type=" + content["type"], wait_until="networkidle")
        admin.locator(".cms-table tbody tr").filter(
            has=admin.get_by_text(content["title"], exact=True)
        ).get_by_role("button", name="Sửa", exact=True).click()
        return admin.get_by_role("dialog")

    image = {
        "name": "fake-member.png",
        "mimeType": "image/png",
        "buffer": (evidence / "media/ui-image.png").read_bytes(),
    }

    def upload_avatar(dialog, label):
        dialog.get_by_label(label, exact=True).set_input_files(image)
        expect(dialog.get_by_role("button", name="Lưu", exact=True)).to_be_enabled()

    try:
        for kind, label in [
            ("music", "Nhạc"),
            ("video", "Video"),
            ("gallery", "Ảnh"),
            ("community", "Cộng đồng"),
            ("homepage", "Trang chủ"),
        ]:
            dialog = new(kind)
            expect(
                dialog.locator(".cms-editor__types button[aria-pressed=true]")
            ).to_have_text(label)
            accepted = dialog.locator(
                ".cms-editor__media input[type=file]"
            ).get_attribute("accept")
            if kind == "music":
                for field in ["Album"]:
                    expect(
                        dialog.get_by_role("combobox", name=field, exact=True)
                    ).to_be_visible()
                expect(
                    dialog.get_by_role("combobox", name="Thể loại", exact=True)
                ).to_have_count(0)
                expect(
                    dialog.get_by_label("Số thứ tự trong album", exact=True)
                ).to_be_visible()
                expect(dialog.get_by_label("Mô tả ngắn", exact=True)).to_have_count(0)
                expect(dialog.get_by_label("Link video", exact=False)).to_have_count(0)
                assert "audio/mpeg" in accepted and "video/" not in accepted
            if kind in {"gallery", "homepage"}:
                assert "audio/" not in accepted and "video/" not in accepted
                expect(dialog.get_by_label("Mô tả ngắn", exact=True)).to_have_count(0)
            if kind == "homepage":
                expect(dialog.get_by_label("Tiêu đề", exact=True)).to_have_count(0)
            if kind == "community":
                expect(
                    dialog.get_by_label("Nội dung bài viết", exact=True)
                ).to_be_visible()
            dialog.get_by_role("button", name="Huỷ", exact=True).click()
        passed("Five CMS forms use selected filter, specific fields and upload formats")

        dialog = new("homepage")
        dialog.get_by_label("Giới thiệu", exact=False).fill(
            "Fake editable homepage introduction"
        )
        dialog.get_by_label("Tên Leader", exact=True).fill("Fake leader with image")
        upload_avatar(dialog, "Ảnh Tên Leader")
        dialog.get_by_role("button", name="+ Thêm nhóm", exact=True).click()
        dialog.get_by_label("Vai trò nhóm 1", exact=True).fill("Fake design")
        dialog.get_by_label("Tên thành viên 1 nhóm 1", exact=True).fill(
            "Fake member one"
        )
        upload_avatar(dialog, "Ảnh Tên thành viên 1 nhóm 1")
        dialog.get_by_role("button", name="+ Thêm người nhóm 1", exact=True).click()
        dialog.get_by_label("Tên thành viên 2 nhóm 1", exact=True).fill(
            "Fake member two"
        )
        dialog.locator(".cms-editor__media input[type=file]").set_input_files(image)
        expect(dialog.locator(".cms-thumb img")).to_have_count(1)
        expect(dialog.locator(".cms-credit-member__image img")).to_have_count(2)
        for width in [320, 390, 768, 1440]:
            admin.set_viewport_size({"width": width, "height": 900})
            assert admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert dialog.evaluate(
                "element => element.scrollWidth <= element.clientWidth + 2"
            )
        admin.screenshot(
            path=str(evidence / "cms-homepage-members.png"), full_page=True
        )
        home = save(dialog, creating=True)
        assert home["title"] == "Trang chủ"
        hero = next(item for item in home["media"] if item["is_primary"])
        member_id = home["body"]["credits"][0]["members"][0]["media_id"]
        avatar = next(item for item in home["media"] if item["media_id"] == member_id)
        api("POST", f"/admin/content/{home['id']}/publish")
        public = context.new_page()
        public.goto(base + "/", wait_until="networkidle")
        expect(public.locator(".home__leader-name")).to_have_text(
            "Fake leader with image"
        )
        expect(public.locator(".home__avatar img")).to_have_count(1)
        expect(public.locator(".home__member-avatar img")).to_have_attribute(
            "src", avatar["url"]
        )
        assert set(
            public.locator(".home__hero-track img").evaluate_all(
                "images => images.map(image => image.getAttribute('src'))"
            )
        ) == {hero["url"]}
        public.get_by_role("button", name="Xem thêm", exact=True).click()
        expect(public.get_by_text("Fake member two", exact=True)).to_be_visible()
        passed(
            "Homepage title, leader, member avatars and separate hero publish correctly"
        )

        dialog = edit(home)
        expect(
            dialog.get_by_label("Tên thành viên 2 nhóm 1", exact=True)
        ).to_have_value("Fake member two")
        expect(dialog.locator(".cms-thumb img")).to_have_count(1)
        upload_avatar(dialog, "Ảnh Tên thành viên 1 nhóm 1")
        updated = save(dialog)
        new_id = updated["body"]["credits"][0]["members"][0]["media_id"]
        assert new_id != member_id
        assert member_id not in {item["media_id"] for item in updated["media"]}
        dialog = edit(updated)
        dialog.locator(".cms-credit-person").first.get_by_role(
            "button", name="Gỡ ảnh", exact=True
        ).click()
        cleared = save(dialog)
        assert len(cleared["media"]) == 2
        public.reload(wait_until="networkidle")
        expect(public.locator(".home__member-avatar img")).to_have_count(0)
        expect(public.locator(".home__member-avatar").first).to_have_text("MO")
        expect(public.locator(".home__hero-track img").first).to_have_attribute(
            "src", hero["url"]
        )
        dialog = edit(cleared)
        dialog.get_by_role("button", name="Xoá nhóm 1", exact=True).click()
        save(dialog)
        public.reload(wait_until="networkidle")
        expect(public.locator(".home__role")).to_have_count(0)
        public.screenshot(
            path=str(evidence / "cms-homepage-public.png"), full_page=True
        )
        passed("Avatar edits and group deletion survive reopening; hero stays separate")

        dialog = new("gallery")
        dialog.get_by_label("Tên bộ ảnh", exact=True).fill("Fake captioned gallery")
        dialog.locator(".cms-editor__media input[type=file]").set_input_files(image)
        dialog.get_by_label("Chú thích ảnh 1", exact=True).fill(
            "Fake per-image caption"
        )
        gallery = save(dialog, creating=True)
        api("POST", f"/admin/content/{gallery['id']}/publish")
        public.goto(base + "/photos", wait_until="networkidle")
        public.get_by_role("button", name="Fake per-image caption", exact=True).click()
        expect(public.locator(".photos__viewer-meta")).to_contain_text(
            "Fake per-image caption"
        )
        dialog = edit(gallery)
        expect(dialog.get_by_label("Chú thích ảnh 1", exact=True)).to_have_value(
            "Fake per-image caption"
        )
        dialog.get_by_label("Chú thích ảnh 1", exact=True).fill("")
        cleared_gallery = save(dialog)
        assert cleared_gallery["media"][0]["caption"] is None
        public.goto(base + "/photos", wait_until="networkidle")
        public.get_by_role("button", name="Fake captioned gallery", exact=True).click()
        expect(public.locator(".photos__viewer-meta")).to_contain_text(
            "Fake captioned gallery"
        )
        passed(
            "Gallery per-image captions save, reopen and render in the public lightbox"
        )

        legacy = api(
            "POST",
            "/admin/content",
            {
                "type": "homepage",
                "title": "Fake legacy home",
                "summary": "Preserve summary",
                "body": {
                    "sections": [{"type": "intro"}],
                    "extra": "Preserve extra",
                    "credits": [
                        {
                            "role": "Legacy",
                            "names": ["Fake legacy one", "Fake legacy two"],
                        }
                    ],
                },
            },
            201,
        )
        created.append(legacy["id"])
        dialog = edit(legacy)
        expect(
            dialog.get_by_label("Tên thành viên 2 nhóm 1", exact=True)
        ).to_have_value("Fake legacy two")
        migrated = save(dialog)
        assert migrated["title"] == legacy["title"]
        assert migrated["summary"] == legacy["summary"]
        assert migrated["body"]["extra"] == "Preserve extra"
        assert migrated["body"]["credits"][0]["names"] == [
            "Fake legacy one",
            "Fake legacy two",
        ]
        passed(
            "Editing legacy names-only credits preserves members and hidden metadata"
        )
        assert not errors, errors
    finally:
        for content_id in reversed(created):
            api("DELETE", f"/admin/content/{content_id}", status=204)
        for media_id in uploads:
            api("DELETE", f"/admin/media/{media_id}", status=204)
        context.close()
