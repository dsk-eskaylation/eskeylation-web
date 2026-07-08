# eskeylation-web

Kho lưu trữ số chính thức của **DSK** — lưu giữ âm nhạc, hình ảnh và khoảnh khắc cho cộng đồng.

Dự án gồm một public site để cộng đồng xem nội dung (âm nhạc, gallery ảnh, community)
và một CMS để biên tập viên tạo, duyệt và xuất bản nội dung.

## Công nghệ

- **Backend:** FastAPI, SQLAlchemy 2.0 (async), Alembic
- **Database & Storage:** Supabase (PostgreSQL managed + Storage)
- **Background:** Celery + Redis
- **Frontend:** React + TypeScript + Vite

## Trạng thái

Đang phát triển theo từng phase — mốc MVP là trang public chạy được với dữ liệu thật.

## Deploy

Frontend và backend chạy **same-origin**: FastAPI tự serve SPA đã build ở
`frontend/dist` (route API luôn ưu tiên, còn lại fallback về `index.html`).
Cách này để cookie phiên (httpOnly, SameSite) hoạt động mà không cần CORS cross-site.

```bash
# Docker (build SPA + backend trong một image)
docker build -t eskaylation .
docker run -p 8000:8000 \
  -e DATABASE_URL=... -e JWT_SECRET=... \
  -e STORAGE_BACKEND=supabase -e SUPABASE_URL=... \
  -e SUPABASE_SERVICE_KEY=... -e STORAGE_BUCKET=media \
  eskaylation
```

Biến môi trường bắt buộc khi prod: `ENVIRONMENT=prod` (mọi giá trị khác `dev`
đều được coi là prod), `JWT_SECRET` (app từ chối chạy prod với secret mặc định),
`DATABASE_URL` (Supabase transaction pooler cổng 6543), `REDIS_URL` (rate limit
dùng chung giữa các worker). Migration chạy tay: `uv run alembic upgrade head`.
