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

## Chạy Redis bằng Docker Compose

Yêu cầu Docker Engine và Docker Compose v2:

```bash
docker compose up -d
```

Compose chỉ chạy Redis. Port `6379` bind vào `127.0.0.1`, chỉ truy cập được
qua localhost trên máy host. Chạy ứng dụng và Celery worker trên máy host với
`REDIS_URL=redis://localhost:6379/0` (giá trị có sẵn trong `.env.example`).

Redis bật AOF và lưu dữ liệu vào volume `redis-data`.

```bash
docker compose logs -f redis
docker compose down
```

`docker compose down` giữ lại dữ liệu volume; thêm `--volumes` sẽ xóa dữ liệu đó.
