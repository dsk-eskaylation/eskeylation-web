"""CMS/public-page regressions, called only by the isolated browser runner."""

from pathlib import Path

from playwright.sync_api import expect


def check_cms_mapping(base, context_factory, login, passed):
    context = context_factory()
    context.add_init_script(
        "const interval=window.setInterval;window.setInterval=(fn,ms,...args)=>"
        "interval(fn,ms===15000?1000:ms,...args)"
    )
    # Exercise embeds without contacting YouTube or playing external content.
    context.route(
        "https://www.youtube.com/**",
        lambda route: route.fulfill(content_type="text/html", body="Fake video"),
    )
    admin = context.new_page()
    created = []
    uploaded = []
    login(admin, "admin")
    csrf = next(c["value"] for c in context.cookies() if c["name"] == "esk_csrf")

    def api(method, path, data=None, expected=200):
        response = admin.request.fetch(
            base + path, method=method, data=data, headers={"X-CSRF-Token": csrf}
        )
        assert response.status == expected, f"{method} {path}: {response.status}"
        return response.json() if expected != 204 else None

    def create(kind, title, body):
        item = api(
            "POST", "/admin/content", {"type": kind, "title": title, "body": body}, 201
        )
        created.append(item["id"])
        api("POST", f"/admin/content/{item['id']}/publish")
        return item

    try:
        first = create(
            "video", "Fake CMS video A", {"embed_url": "https://youtu.be/abcdefghijk"}
        )
        create(
            "video", "Fake CMS video B", {"embed_url": "https://youtu.be/123456789ab"}
        )
        public = context.new_page()
        public.goto(base + "/video", wait_until="networkidle")
        public.locator(".video-card").filter(has_text=first["title"]).click()
        expect(public.locator(".video-hero iframe")).to_have_attribute(
            "src", "https://www.youtube.com/embed/abcdefghijk?autoplay=1"
        )
        api(
            "PATCH",
            f"/admin/content/{first['id']}",
            {
                "title": "Fake CMS video A edited",
                "body": {"embed_url": "https://www.youtube.com/embed/123456789ab"},
            },
        )
        expect(public.locator(".video-hero__title")).to_have_text(
            "Fake CMS video A edited", timeout=6000
        )
        expect(public.locator(".video-hero iframe")).to_have_attribute(
            "src", "https://www.youtube.com/embed/123456789ab?autoplay=1"
        )
        api("POST", f"/admin/content/{first['id']}/unpublish")
        expect(public.locator(".video-hero__title")).not_to_have_text(
            "Fake CMS video A edited", timeout=6000
        )
        expect(public.locator(".video-hero iframe")).to_have_count(0)
        passed(
            "CMS video edits refresh selected title/source; unpublish stops playback"
        )
        public.locator(".video-hero__poster").click()
        create(
            "video",
            "Fake newer CMS video",
            {"embed_url": "https://youtu.be/123456789ac"},
        )
        expect(
            public.locator(".video-card").filter(has_text="Fake newer CMS video")
        ).to_be_visible(timeout=6000)
        expect(public.locator(".video-hero__title")).to_have_text("Fake CMS video B")
        passed("Playing the initial video pins its ID when newer videos are published")
        public.close()

        home = create(
            "homepage",
            "Fake mapped homepage",
            {
                "intro": "Fake CMS introduction",
                "maintain": ["Fake support before"],
                "sections": [{"type": "intro", "text": "Fake"}],
            },
        )
        public = context.new_page()
        public.goto(base + "/", wait_until="networkidle")
        expect(public.locator(".home__about-text")).to_have_text(
            "Fake CMS introduction"
        )
        api(
            "PATCH",
            f"/admin/content/{home['id']}",
            {
                "body": {
                    **home["body"],
                    "intro": "Fake introduction updated",
                    "maintain": ["Fake support after"],
                }
            },
        )
        expect(public.locator(".home__about-text")).to_have_text(
            "Fake introduction updated", timeout=6000
        )
        expect(public.locator(".home__maintain-info")).to_contain_text(
            "Fake support after"
        )
        passed("Homepage intro and support follow CMS edits without reload")
        image = admin.request.get(base + "/media/ui-image.png")
        assert image.status == 200
        response = admin.request.post(
            base + "/admin/media",
            headers={"X-CSRF-Token": csrf},
            multipart={
                "file": {
                    "name": "fake-home.png",
                    "mimeType": "image/png",
                    "buffer": image.body(),
                }
            },
        )
        assert response.status == 201
        media = response.json()
        uploaded.append(media["id"])
        api(
            "PATCH",
            f"/admin/content/{home['id']}",
            {"media": [{"media_id": media["id"], "is_primary": True}]},
        )
        expect(public.locator(".home__hero-track img").first).to_have_attribute(
            "src", media["url"], timeout=6000
        )
        api("PATCH", f"/admin/content/{home['id']}", {"media": []})
        expect(public.locator(".home__hero-track img").first).not_to_have_attribute(
            "src", media["url"], timeout=6000
        )
        passed(
            "Homepage uploaded hero images and default fallback follow CMS media edits"
        )
        public.close()

        song = create(
            "music",
            "Fake lyric review song",
            {
                "artist": "Fake artist",
                "audio_url": "/media/ui-tone.wav",
                "lyrics": "Fake original lyrics",
            },
        )
        api(
            "POST",
            f"/api/music/{song['id']}/lyrics",
            {"body": "Fake contributed lyrics\nSecond line"},
            201,
        )
        public = context.new_page()
        public.goto(base + "/music", wait_until="networkidle")
        public.locator(".music__row").filter(has_text=song["title"]).click()
        public.get_by_role("button", name="Lời bài hát", exact=True).click()
        expect(public.locator(".pbpanel__lyrics")).to_have_text("Fake original lyrics")

        admin.goto(base + "/cms", wait_until="networkidle")
        admin.get_by_role("button", name="Kiểm duyệt", exact=True).click()
        section = admin.get_by_role("region", name="Duyệt lời nhạc")
        item = section.locator(".cms-lyrics__item").filter(has_text=song["title"])
        expect(item).to_be_visible()
        item.get_by_role("button", name="Duyệt lời nhạc", exact=True).click()
        admin.get_by_role("dialog").get_by_role(
            "button", name="Duyệt và cập nhật", exact=True
        ).click()
        expect(item).to_have_count(0)
        expect(public.locator(".pbpanel__lyrics")).to_have_text(
            "Fake contributed lyrics\nSecond line", timeout=6000
        )
        section.get_by_role("group", name="Trạng thái lời nhạc").get_by_role(
            "button", name="Đã duyệt", exact=True
        ).click()
        expect(
            section.locator(".cms-lyrics__item").filter(has_text=song["title"])
        ).to_be_visible()
        passed(
            "Admin lyric approval/history updates lyrics of the currently playing song"
        )

        api(
            "POST",
            f"/api/music/{song['id']}/lyrics",
            {"body": "Fake rejected lyrics"},
            201,
        )
        section.get_by_role("group", name="Trạng thái lời nhạc").get_by_role(
            "button", name="Chờ duyệt", exact=True
        ).click()
        item = section.locator(".cms-lyrics__item").filter(has_text=song["title"])
        item.get_by_role("button", name="Từ chối lời nhạc", exact=True).click()
        admin.get_by_role("dialog").get_by_role(
            "button", name="Xác nhận từ chối", exact=True
        ).click()
        expect(item).to_have_count(0)
        assert (
            api("GET", f"/api/music/{song['slug']}")["body"]["lyrics"]
            == "Fake contributed lyrics\nSecond line"
        )
        section.get_by_role("group", name="Trạng thái lời nhạc").get_by_role(
            "button", name="Đã từ chối", exact=True
        ).click()
        expect(section.locator(".cms-lyrics__body")).to_contain_text(
            "Fake rejected lyrics"
        )
        public.close()
        passed("Admin lyric rejection/history keeps current lyrics unchanged")

        admin.get_by_role("complementary", name="Điều hướng quản trị").get_by_role(
            "button", name="Nhạc", exact=True
        ).click()
        row = admin.locator(".cms-table tbody tr").filter(has_text=song["title"])
        row.get_by_role("button", name="Sửa", exact=True).click()
        dialog = admin.get_by_role("dialog")
        expect(dialog.get_by_label("Lời bài hát", exact=True)).to_have_value(
            "Fake contributed lyrics\nSecond line"
        )
        dialog.get_by_label("Lời bài hát", exact=True).fill("Fake lyrics edited in CMS")
        dialog.get_by_role("button", name="Lưu", exact=True).click()
        expect(dialog).to_have_count(0)
        assert (
            api("GET", f"/api/music/{song['slug']}")["body"]["lyrics"]
            == "Fake lyrics edited in CMS"
        )
        passed("CMS music form can edit published lyrics directly")
    except BaseException:
        evidence = Path(".local/browser-checks")
        evidence.mkdir(parents=True, exist_ok=True)
        admin.screenshot(path=str(evidence / "cms-mapping-failure.png"), full_page=True)
        (evidence / "cms-mapping-failure.html").write_text(
            admin.content(), encoding="utf-8"
        )
        raise
    finally:
        for content_id in reversed(created):
            api("DELETE", f"/admin/content/{content_id}", expected=204)
        for media_id in uploaded:
            api("DELETE", f"/admin/media/{media_id}", expected=204)
        context.close()
