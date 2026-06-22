# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Ngôn ngữ: dự án và tài liệu kế hoạch bằng tiếng Việt — giữ comment/commit/PR bằng tiếng Việt khi phù hợp.

## Trạng thái hiện tại

Repo đang ở **Phase 0** (setup nền tảng). Hiện mới chỉ có scaffold `uv` với `main.py` hello-world — toàn bộ kiến trúc bên dưới là **đích đến**, chưa được dựng. Khi thêm code mới, bám theo cấu trúc thư mục và nguyên tắc trong file này.

Nguồn chân lý cho kế hoạch: `Eskaylation_Ke_hoach_trien_khai_v2.docx` (10 phase, MVP = hết Phase 4).

## Lệnh thường dùng

Quản lý môi trường Python bằng **uv** (không dùng pip/venv thủ công). Python **>=3.13**.

```bash
uv sync                 # cài dependencies từ pyproject.toml + uv.lock
uv run main.py          # chạy entrypoint hiện tại
uv add <package>        # thêm dependency (cập nhật pyproject.toml + lock)
uv add --dev <package>  # thêm dev dependency
```

Khi backend đã dựng, các lệnh dự kiến (cập nhật lại khi có thực tế):
```bash
uv run uvicorn app.main:app --reload     # FastAPI dev server
uv run alembic upgrade head              # áp migration
uv run alembic revision --autogenerate -m "msg"   # tạo migration
uv run celery -A app.workers worker -l info       # Celery worker
uv run pytest tests/path::test_name      # chạy một test đơn lẻ
```

## Tech Stack

- **Backend:** FastAPI (async), SQLAlchemy 2.0 + Alembic, Pydantic Settings
- **DB:** Supabase (PostgreSQL managed) — **không self-host**. Kết nối async **phải qua connection pooler (PgBouncer)**
- **Background:** Celery + Redis (xử lý ảnh/video không chặn UI)
- **Media:** Pillow, python-magic, ffprobe; lưu trên **Supabase Storage** (S3-compatible + CDN)
- **Auth:** JWT + RBAC **tự viết trong FastAPI** (không dùng Supabase Auth — tránh vendor lock-in); bleach chống XSS/SSRF
- **Frontend:** React + TypeScript + Vite (dark theme, UI động: feed blur, modal, drag reorder qua dnd-kit)
- **Testing:** Playwright (visual regression đa viewport)

## Kiến trúc & cấu trúc thư mục dự kiến

Backend tổ chức theo layer: `app/` chứa `models/` (SQLAlchemy), `schemas/` (Pydantic), `routers/` (endpoints), `services/` (business logic), `workers/` (Celery tasks).

Điểm kiến trúc cần đọc nhiều file mới hiểu:

- **Tách Public API khỏi draft (nguyên tắc số 1):** endpoint public **chỉ** trả nội dung `published`. Admin fields bị ẩn bằng **Pydantic response schema riêng** — không tái dùng schema nội bộ cho output public. Đây là ranh giới bảo mật, không phải tùy chọn.
- **Vòng đời nội dung:** `draft → published → archived`. Publish phải validate required media + metadata trước khi cho qua.
- **Quan hệ Content ↔ Media là M-N có thuộc tính:** bảng nối `content_media` mang `caption`, `order`, cờ `primary`. Đừng mô hình hóa thành M-N đơn thuần.
- **Storage abstraction:** mọi truy cập media đi qua một storage **interface** (dựng từ Phase 0). Supabase Storage chỉ là một implementation. **Không** gọi thẳng SDK Supabase trong service/router — bỏ qua lớp này sẽ phải refactor lớn khi đổi backend.
- **RBAC:** ba vai trò `admin / editor / author`, kiểm tra bằng FastAPI dependency.
- **Preview tái dùng component public:** CMS preview (Phase 7) render bằng **chính** component công khai của frontend, không dựng bản sao. Preview cấp qua token có hạn, chỉ mở draft đã chọn; khách chưa đăng nhập không bao giờ list được draft.
- **Frontend tái dùng modal:** community feed dùng lại photo modal — không duplicate component.

## Lộ trình (build-able theo thứ tự)

Mỗi phase tạo ra phần chạy được trước khi sang phase kế. **MVP = hết Phase 4** (trang public chạy với dữ liệu thật, demo được).

| Phase | Nội dung |
|-------|----------|
| 0 | Setup nền tảng, storage abstraction, migration đầu |
| 1 | Models cốt lõi (Content/Media/User), JWT + RBAC, vòng đời nội dung |
| 2 | Public API (chỉ published, search/filter/pagination) |
| 3 | Frontend shell, design tokens, homepage |
| 4 | ★ Các trang nội dung (music/photo/community) — **mốc MVP** |
| 5 | Media Manager (upload, Celery variants, library, picker) |
| 6 | CMS quản lý nội dung (editor, publishing workflow) |
| 7 | CMS Preview |
| 8 | Bảo mật (sanitize XSS, chống SSRF), hiệu năng, Playwright |
| 9 | Tối ưu Supabase Storage / CDN |

## Nguyên tắc KHÔNG được cắt scope (kể cả khi gấp deadline)

1. **Tách draft khỏi Public API** (Phase 1) — rủi ro lộ nội dung chưa xuất bản.
2. **Validate MIME/size + sanitize XSS** (Phase 5/8) — rủi ro bảo mật trực tiếp.
3. **Storage abstraction** (Phase 0) — bỏ qua phải refactor lớn.

Có thể hoãn khi cần MVP nhanh: Phase 7 (Preview), Phase 9 (CDN), media variants (tạm dùng ảnh gốc), bulk/folder của Media Manager, rút gọn visual regression.
