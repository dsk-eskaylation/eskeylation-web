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
- 332 test backend xanh (`pytest`), `ruff check` xanh; frontend `tsc -b`, `oxlint` (0 lỗi), `vite build` xanh.

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

## 7. Kết quả review code (Open Code Review, chế độ delegate)

- **Phạm vi:** toàn bộ diff `main..khiem-dev`, 52 file (22 backend, 30 frontend), review theo bộ luật của OCR cho từng nhóm file. **Coverage 52/52 (100%)**, không file nào bỏ qua. 5 file bị OCR loại theo luật mặc định: 3 file test, `frontend/src/genres.ts` (đã xoá), `deploy/nginx/security-headers.conf`.
- **Kết quả:** không có lỗi critical/high (không lỗ bảo mật, không mất dữ liệu ở mức nghiêm trọng). Có 9 lỗi medium, **đã sửa hết** trong commit "Fix album/music review findings".
- **Đã kiểm và ổn:** tên index/constraint khớp giữa model và migration; downgrade đúng thứ tự; seed chạy lại không đổi kết quả; oEmbed chỉ gọi endpoint cố định (không SSRF, có timeout và rate limit); phân quyền album (tạo/sửa/xoá chỉ editor/admin); query tham số hoá (không SQL injection); CSP khớp ở cả 3 nơi; trang Ảnh (cuộn tải thêm, vuốt).

### Lỗi đã phát hiện và cách sửa

| # | Chỗ | Lỗi | Đã sửa | Kiểm chứng |
|---|---|---|---|---|
| 1 | `CmsAlbums.tsx` | Xoá album xong hộp xác nhận không đóng; bấm lại → 404 không báo; lỗi 403/500 không hiện | Đóng hộp ngay khi xác nhận; `try/catch` báo lỗi bằng toast | Trình duyệt: tạo album tạm → xoá → hộp đóng, album biến mất, có thông báo |
| 2 | `Cms.tsx` (form sửa bài) | Chỉ đổi album/thể loại/link SoundCloud rồi đóng form → mất thay đổi, không cảnh báo | Thêm `albumId, trackNo, category, sourceUrl, coverLink` vào phần so sánh "có thay đổi chưa lưu" | Trình duyệt: đổi album → Esc → hiện "Thay đổi chưa lưu" |
| 3 | `Music.tsx`, `MusicAll.tsx` | Đổi album nhanh: danh sách album cũ còn hiện, bấm Phát phát nhầm album cũ; album 404 không báo | Chỉ dùng dữ liệu khi khớp album đang chọn; lúc chờ hiện "Đang tải album…", khoá Phát/Trộn; lưới cũ `aria-busy` + `inert`; 404 hiện "Không tìm thấy album này." | Trình duyệt: Waking Life → Diss Tracks, album không tồn tại, đổi album trên trang lưới |
| 4 | `PlayerContext.tsx` | Đang mở player SoundCloud mà bấm Next/Prev/phím media → mp3 và SoundCloud phát cùng lúc | Đóng player nhúng ngay trong `startTrack` (mọi đường phát mp3 đều qua đây) và trong handler `play` của MediaSession | Typecheck/build; **chưa thử trên trình duyệt** (dữ liệu local chưa có bài dạng link) |
| 5 | `EmbedDock.css` | Khung player nhúng che panel lời/hàng chờ của PlayerBar và nút điều khiển trên màn nhỏ | Chuyển khung lên góc trên phải, ngay dưới thanh nav; `z-index` dưới nav để menu tài khoản không bị che | Tính từ CSS; **chưa đo trên trình duyệt** |
| 6 | `Dropdown.tsx` | Trình đọc màn hình không đọc lựa chọn đang đứng (`aria-activedescendant` trên `<button>`); có thể crash nếu danh sách đổi lúc đang mở | `role="combobox"` cho nút; kẹp chỉ số đang chọn theo số lựa chọn, bỏ qua khi lựa chọn không còn | Trình duyệt: kiểm `role="combobox"`, chọn album bằng bàn phím |
| 7 | `content_admin.py` | Hai người cùng gán một số thứ tự vào cùng album, hoặc album bị xoá giữa chừng → lỗi 500 | Bắt `IntegrityError` ở nhánh sửa bài → rollback + 409 với câu báo trung tính (dùng chung cho tạo/sửa/nhân bản) | Test hiện có; **chưa có test tái hiện race** |
| 8 | `albums.py`, `content_admin.py`, migration `o4e6a8c0d2f3` | Xoá album để lại `track_no` trên bài (bài lẻ vẫn có số thứ tự; gán album mới báo trùng số khó hiểu) | Xoá album thì xoá `track_no` của các bài; đổi album mà không gửi `track_no` thì đặt lại về trống; `downgrade` của migration dữ liệu cũng xoá `track_no` trước | Test mới `test_moving_track_without_number_resets_it` + assert trong test xoá album; chạy lại `downgrade/upgrade` migration |
| 9 | `Cms.tsx`, `Cms.css` (mobile) | Sidebar đã đóng vẫn Tab vào được link ẩn; Esc không đóng | Ẩn hẳn sidebar khi đóng (`visibility: hidden`); Esc đóng; mở thì focus link đầu, đóng bằng Esc/lớp phủ thì trả focus về nút menu | Typecheck/build; **chưa thử trên khổ hẹp thật** |

### Lỗi mức low chưa sửa (để lại cho vòng sau)
- Đổi tên album làm slug đổi theo → link album đã chia sẻ thành 404 (content thì giữ slug khi đổi tên).
- `Content.album` dùng `lazy="selectin"` thêm một lượt query; có thể `joinedload` riêng cho các query danh sách công khai.
- Trên iOS, menu/dropdown đóng bằng `mousedown` có thể không đóng khi chạm ra ngoài (nên dùng `pointerdown`); `RowMenu` khai báo `role="menu"` nhưng chưa có điều hướng bằng phím mũi tên.
- Trang lưới: chọn album từ lưới album rồi Back thì rời trang (đang dùng `replace`); lưới album chưa có trạng thái tải/lỗi.
- Nút Phát/Trộn vẫn bật khi danh sách chỉ toàn bài dạng link.
- Theo luật OCR: vài chỗ ternary lồng nhau và một inline style ở `Cms.tsx`.
