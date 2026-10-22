"""CMS worker status and retry UI using fake responses on localhost only."""

from playwright.sync_api import expect


def check_media_jobs(base, context_factory, login, passed, evidence):
    assert base.startswith("http://127.0.0.1:")
    ctx = context_factory()
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    status = {
        "enabled": True,
        "worker_online": False,
        "counts": {"failed": 1, "skipped": 2},
        "items": [
            {
                "id": 987654,
                "mime_type": "video/mp4",
                "processing_status": "failed",
                "processing_attempts": 3,
                "processing_error_code": "processing_timeout",
            }
        ],
    }
    page.route("**/admin/media/jobs", lambda route: route.fulfill(json=status))

    def retry(route):
        assert route.request.method == "POST"
        status["counts"] = {"pending": 1, "skipped": 2}
        status["items"][0]["processing_status"] = "pending"
        status["items"][0]["processing_attempts"] = 0
        status["items"][0]["processing_error_code"] = None
        route.fulfill(status=202, json={"id": 987654, "processing_status": "pending"})

    page.route("**/admin/media/987654/process", retry)
    try:
        login(page, "admin")
        page.get_by_role("button", name="Tổng quan", exact=True).click()
        panel = page.get_by_role("region", name="Xử lý ảnh và video")
        expect(panel).to_be_visible()
        expect(panel.get_by_text("Tạm gián đoạn", exact=True)).to_be_visible()
        expect(panel.get_by_text("File xử lý quá lâu.", exact=True)).to_be_visible()
        panel.get_by_role("button", name="Thử lại", exact=True).click()
        expect(panel.get_by_text("Chờ xử lý · 0 lần xử lý", exact=True)).to_be_visible()
        expect(panel.get_by_role("button", name="Thử lại", exact=True)).to_have_count(0)
        passed("CMS media worker outage keeps jobs visible and retry queues once")
        page.set_viewport_size({"width": 390, "height": 844})
        panel.scroll_into_view_if_needed()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(path=str(evidence / "media-jobs-mobile.png"))
        assert not errors, errors
        passed("Media job dashboard fits mobile and has no browser errors")
    finally:
        ctx.close()
