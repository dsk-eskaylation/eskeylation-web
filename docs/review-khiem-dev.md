# Review nhánh `khiem-dev`

> Đọc trước khi review code và **bắt buộc** đọc mục "Trước khi migrate" trước khi merge vào `main`.
> Merge vào `main` là CI tự deploy và tự chạy `alembic upgrade head` trên DB production.
> Review mô hình dữ liệu chung của dự án: xem `docs/db-review.md`.

## 1. Nhánh này thay đổi gì

| Nhóm | Thay đổi chính |
|---|---|
| Album nhạc | Bảng `albums`; `contents.album_id` + `track_no`; 13 album được gán sẵn cho 118/174 bài; API `/api/albums`, `/api/albums/{slug}`, `/api/music?album=`, `/api/music?singles=true`, `/api/music/genres`; CMS tab Album |
| Nhạc từ link | Thêm nhạc bằng link SoundCloud/YouTube/Vimeo (cột `source_url`, `source_provider`, `cover_url`); oEmbed tự điền tên, nghệ sĩ, ảnh bìa; phát bằng player nhúng chính thức |
| Trang Nghe nhạc | Dropdown lọc album (có ảnh bìa), lọc thể loại (ẩn khi chưa có dữ liệu), Phát/Trộn; tìm kiếm **chỉ theo tên bài**; link "Xem lưới album" |
| Trang lưới nhạc `/music/all` | Lọc album; chế độ Bài hát / Album (lưới thẻ album) |
| Trang Ảnh | Bỏ phân trang, tự tải thêm khi cuộn; vuốt trái/phải trong trình xem ảnh |
| Giao diện chung | Nền texture dùng chung mọi trang; thanh nav kiểu kính mờ đặc; nút tài khoản cùng chất liệu |
| CMS | Bố cục sidebar (tham khảo Soulari admin); mỗi loại nội dung một tab; bảng nội dung + menu ⋯ |

Tương thích ngược: mọi field API mới đều là field thêm, client cũ không bị ảnh hưởng. Riêng **tìm kiếm trên trang `/music`** đổi hành vi (không còn khớp tên nghệ sĩ).

## 2. Migration (theo thứ tự chạy)

| Revision | Loại | Nội dung | Khoá / chi phí |
|---|---|---|---|
| `m2c4e6a8b0d1` | Schema | `contents`: thêm `source_url`, `source_provider`, `cover_url` + 3 CHECK | Cột nullable không default → chỉ sửa catalog. CHECK quét bảng `contents` (vài trăm dòng) |
| `n3d5f7b9c1e2` | Schema | Bảng `albums` (+ RLS deny-all như các bảng khác); `contents.album_id` (FK `ON DELETE SET NULL`), `track_no`, index, unique partial `(album_id, track_no)`, 2 CHECK | Như trên |
| `o4e6a8c0d2f3` | **Dữ liệu** | Tạo 13 album; gán album + số thứ tự cho 118 bài theo **slug**; làm sạch 47 tên nghệ sĩ (`DSK (Waking Life 01)` → `DSK`) | UPDATE theo slug, vài trăm dòng |
| `p5f7b9d1e3a4` | **Dữ liệu** | Gán ảnh bìa cho 13 album | 13 UPDATE |

Phần schema đặt `SET LOCAL lock_timeout = '5s'` giống các migration trước.

### Tính an toàn của migration dữ liệu
- Chỉ gán album cho bài **chưa có album** (`album_id IS NULL`); chỉ sửa tên nghệ sĩ khi giá trị **vẫn đúng như cũ**; chỉ đặt ảnh bìa khi album **chưa có ảnh**. Admin đã sửa tay trên prod trước khi deploy thì không bị ghi đè; chạy lại không đổi kết quả.
- Bài không khớp slug (đã bị xoá/đổi slug) bị bỏ qua, không lỗi.
- `downgrade()` khôi phục tên nghệ sĩ cũ (chỉ những dòng chưa bị sửa tiếp) và xoá 13 album; `ON DELETE SET NULL` tự gỡ liên kết bài.

### Đã kiểm chứng
- Chạy `upgrade → downgrade → upgrade` trên một DB có đúng 174 bài nhạc thật (slug/title/artist lấy từ API public): 118 bài vào đúng 13 album, mọi album có tracklist đều đủ số thứ tự và không trùng, 0 tên nghệ sĩ còn tag, downgrade trả về nguyên trạng.
- 331 test backend xanh (`pytest`), `ruff check` xanh; frontend `tsc -b`, `oxlint`, `vite build` xanh.

## 3. Trước khi migrate trên production (checklist)

1. **Backup DB** (Supabase: Database → Backups, hoặc `pg_dump`). Workflow deploy hiện **không** tự backup trước khi migrate.
2. Kiểm tra head hiện tại là `f42a19c72e10`:
   ```sql
   SELECT version_num FROM alembic_version;
   ```
3. Đếm trước để so sánh sau:
   ```sql
   SELECT count(*) FROM contents WHERE type = 'music';  -- dự kiến 174
   SELECT count(*) FROM contents
   WHERE type = 'music' AND body->>'category' IS NOT NULL;  -- dự kiến 0
   ```
   Nếu có bài đã có `category` ngoài danh sách `LIFE RAP, LOVE RAP, DISSIN', GANGSTA, THỂ NGHIỆM, KHÁM PHÁ` thì sau deploy **sửa bài đó trong CMS sẽ bị 422** cho tới khi chọn lại thể loại hợp lệ.
4. (Khuyến nghị) chạy thử `alembic upgrade head` trên bản sao DB (branch Supabase hoặc restore backup vào DB tạm).
5. Sau khi deploy, kiểm tra:
   ```sql
   SELECT a.title, count(c.id) AS tracks, count(c.track_no) AS numbered
   FROM albums a LEFT JOIN contents c ON c.album_id = a.id
   GROUP BY a.title, a.position ORDER BY a.position;
   -- 13 dòng; tổng tracks = 118

   SELECT count(*) FROM contents
   WHERE type = 'music'
     AND body->>'artist' ~* '(waking life|saigon smoking|vol [34]\.|at kong|verse$)';
   -- dự kiến 0
   ```
6. Rollback nếu cần: `alembic downgrade f42a19c72e10` (gỡ cả 4 revision), hoặc restore backup.

## 4. Việc ngoài code cần làm khi deploy

- **CSP của nginx phải cập nhật tay.** `deploy/nginx/security-headers.conf` thêm `https://w.soundcloud.com` vào `frame-src`, nhưng file này **không** được CI deploy — cần chạy lại `scripts/nginx_security.py` trên server. Nếu không, player SoundCloud bị chặn trên prod (trình duyệt áp dụng cả CSP header lẫn meta).
- Không có biến môi trường mới. Danh sách thể loại nằm ở `Settings.music_genres` (override qua env nếu cần).

## 5. Điểm cần người review quyết định

- **Gán album độ tin cậy trung bình** (nguồn: kho Drive và SoundCloud do fan gom): nhóm "Những Ngày Ở Kong", "Prod. TaiHeo"; thứ tự bài Vol. 4 (lấy qua tóm tắt RateYourMusic); F#m thuộc Vol. 3. Sửa được trong CMS sau deploy.
- **"Một Lần Nữa"** có trong cả Waking Life và EP DSK Kollek; vì mỗi bài chỉ thuộc 1 album nên đang để ở Waking Life.
- **Ảnh bìa**: DSK Kollek (Spotify) và TTNMP Vol. 1–4 (thumbnail video chính thức) là ảnh liên kết ngoài (`i.scdn.co`, `i.ytimg.com`); các album còn lại dùng ảnh từ thư viện Ảnh của chính site. Nên tải ảnh bìa lên S3 qua CMS để không phụ thuộc CDN bên ngoài.
- 56 bài không đủ căn cứ nên để "Bài lẻ"; 0/174 bài có thể loại → bộ lọc thể loại đang ẩn cho tới khi admin gán.

## 6. Chưa kiểm thử

- Giao diện mobile của CMS và trang nhạc chưa kiểm trên khổ hẹp thật.
- Upload file trong CMS (cần AWS key) và Celery worker.
- Chế độ `PUBLIC_CONTENT_SOURCE=drive`: album/`singles` trả rỗng có chủ đích (catalog Drive không có album).
