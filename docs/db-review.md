# Review mô hình dữ liệu Eskaylation

> Phạm vi: NGHIÊN CỨU + KHUYẾN NGHỊ. Không đổi schema/model/migration trong lần này.
> Nguồn: `app/models/*.py`, `alembic/versions/*.py`, query nóng `app/services/content_query.py`, logic CMS `app/services/content_admin.py`, và soi DB live (read-only) qua asyncpg.

## Tóm tắt

Schema cốt lõi đã tốt và đúng định hướng (M-N có thuộc tính cho `content_media`, FTS tsvector + unaccent với `f_unaccent` IMMUTABLE, timestamptz, tách Public API). Điểm yếu chính nằm ở **thiếu các ràng buộc toàn vẹn quanh `content_media`** (nhiều `is_primary=true`, trùng media, trùng position) và **thiếu composite/partial index cho query public nóng** (`type + status + published_at`). Đây là hai nhóm đáng làm sớm. Phần còn lại (slug unique toàn cục, audit, versioning, cursor pagination) là đánh đổi thiết kế, nên xử lý theo phase chứ không gấp.

### Trạng thái soi DB live
ĐÃ KẾT NỐI được tới Supabase pooler (read-only). Schema thực tế khớp với migration. Bảng gần như rỗng: `contents` chỉ có 2 dòng `gallery/draft`, `media`=0, `content_media`=0. Vì rỗng nên planner chạy **Seq Scan** cho cả list lẫn count (đúng và rẻ ở quy mô này) — `EXPLAIN ANALYZE` **chưa phản ánh hành vi ở quy mô lớn**. Phân tích hiệu năng dưới đây dựa trên suy luận tĩnh về kế hoạch query khi dữ liệu tăng, không phải số đo live.

Ràng buộc thực tế trong DB (xác nhận qua `information_schema`): chỉ có NOT NULL + PK + FK + UNIQUE(`slug`), UNIQUE(`storage_key`), UNIQUE(`email`). **Không có** CHECK enum, **không có** unique nào trên `content_media`, **không có** index trên `published_at` hay `author_id`.

---

## Bảng phát hiện theo ưu tiên

### CAO

#### C1. `content_media`: cho phép nhiều `is_primary=true` trên cùng content
- **Vị trí:** `app/models/media.py:40`, migration `4750def72355` (không có constraint). Logic `_replace_media` (`content_admin.py:44-53`) chèn nguyên si `is_primary` từ input, không kiểm tra số lượng primary.
- **Rủi ro thực tế:** CMS gửi 2 media cùng `is_primary=true` → `content_to_out` (`serialize.py`) trả nhiều primary → frontend chọn ảnh đại diện không xác định (thumbnail feed/gallery nhảy lung tung). Đây là **bug toàn vẹn thật**, không phải tùy chọn.
- **Đề xuất:** unique partial index đảm bảo tối đa 1 primary mỗi content.
```sql
CREATE UNIQUE INDEX uq_content_media_one_primary
  ON content_media (content_id)
  WHERE is_primary;
```
- **Lưu ý ứng dụng:** sau khi thêm, `_replace_media` cần đảm bảo không quá 1 primary (validate ở schema `ContentMediaIn` hoặc service), nếu không INSERT sẽ ném IntegrityError.

#### C2. `content_media`: thiếu UNIQUE(content_id, media_id) — cho phép gắn trùng media
- **Vị trí:** `app/models/media.py:31-40` (PK chỉ là `id` surrogate), migration `4750def72355:67-77`.
- **Rủi ro thực tế:** cùng một media gắn 2 lần vào 1 content → ảnh lặp trong gallery, và nếu cả hai cùng primary thì càng loạn. `_replace_media` xóa-rồi-chèn nên ít rủi ro qua đường CMS, nhưng DB không bảo vệ được nếu có đường ghi khác (import, script, bug).
- **Đề xuất:**
```sql
ALTER TABLE content_media
  ADD CONSTRAINT uq_content_media_content_media UNIQUE (content_id, media_id);
```
- **Đánh đổi:** nếu chủ ý cho phép cùng 1 ảnh xuất hiện 2 vị trí (hiếm với gallery), bỏ qua. Mặc định nên thêm.

#### C3. Thiếu composite/partial index cho query public nóng
- **Vị trí:** query `content_query.py:10-14, 54` — `WHERE type=? AND status='published' ORDER BY published_at DESC, id DESC`. Index hiện có chỉ là 2 btree đơn lẻ `ix_contents_type`, `ix_contents_status` (xác nhận qua `pg_indexes`).
- **Rủi ro thực tế:** ở quy mô vài nghìn–vài chục nghìn content, planner phải bitmap-and 2 index đơn lẻ rồi **sort toàn bộ** theo `published_at` cho mỗi trang. List public là route nóng nhất (Phase 2/4). Càng sâu trang (offset lớn) càng đắt. Live chưa thấy vì bảng rỗng.
- **Đề xuất:** partial index phủ đúng predicate published + thứ tự sort, kèm `id` để khớp tie-break.
```sql
CREATE INDEX ix_contents_public_list
  ON contents (type, published_at DESC, id DESC)
  WHERE status = 'published';
```
Index partial này nhỏ (chỉ published) và cho phép index-scan trả thẳng thứ tự, bỏ bước sort. Khi có index này, hai index đơn `ix_contents_type` / `ix_contents_status` phần lớn thừa cho route public (vẫn có thể giữ `status` cho truy vấn admin lọc theo status).

#### C4. Thiếu CHECK ràng buộc enum ở tầng DB (`native_enum=False`)
- **Vị trí:** `enums.py`, model dùng `Enum(..., native_enum=False)` → DB lưu `VARCHAR` thuần, không có enum type, không có CHECK (xác nhận: `contents.type/status` là `character varying`, không CHECK nào ngoài NOT NULL).
- **Rủi ro thực tế:** bất kỳ đường ghi nào ngoài ORM (SQL tay, migration data, script seed) có thể đặt `status='publish'` (sai chính tả) hoặc `type='gallary'`. Khi đó `_published()` lọc `status='published'` âm thầm bỏ sót, hoặc nội dung lọt sai loại. Lỗi câm, khó truy.
- **Đề xuất:** thêm CHECK (giữ lưu dạng text, không bắt buộc đổi sang native enum):
```sql
ALTER TABLE contents ADD CONSTRAINT ck_contents_type
  CHECK (type IN ('music','gallery','community','homepage'));
ALTER TABLE contents ADD CONSTRAINT ck_contents_status
  CHECK (status IN ('draft','published','archived'));
ALTER TABLE users ADD CONSTRAINT ck_users_role
  CHECK (role IN ('admin','editor','author'));
```
- **Đánh đổi:** mỗi lần thêm enum value phải sửa CHECK. Chấp nhận được vì enum rất ổn định.

---

### TRUNG BÌNH

#### M1. Thiếu invariant "published ⇒ published_at NOT NULL"
- **Vị trí:** `published_at` nullable (`content.py:37`). `publish()` (`content_admin.py:118-124`) set `published_at` khi publish, NHƯNG `set_status()` (`content_admin.py:127-132`) đổi status **tùy ý** không đụng `published_at`.
- **Rủi ro thực tế:** gọi `set_status(content, published)` (thay vì `publish()`) tạo ra content `published` với `published_at=NULL`. Query list sort `published_at DESC` đẩy NULL về cuối/đầu bất định → content tụt khỏi trang đầu hoặc thứ tự sai. Cũng bỏ qua `validate_for_publish`. Đây là bug logic + thiếu lưới an toàn DB.
- **Đề xuất (DB lưới an toàn):**
```sql
ALTER TABLE contents ADD CONSTRAINT ck_contents_published_at
  CHECK (status <> 'published' OR published_at IS NOT NULL);
```
- **Đề xuất (ứng dụng):** `set_status` khi chuyển sang published nên đi qua `publish()` hoặc tự set `published_at`. (Ghi nhận để team xử lý, không sửa trong lần review này.)

#### M2. Thiếu UNIQUE(content_id, position) — position có thể trùng
- **Vị trí:** `content_media.position` default 0 (`media.py:39`), không unique.
- **Rủi ro thực tế:** nhiều media cùng `position` → thứ tự hiển thị không xác định (order_by position rồi tie-break ngầm theo id). Ít nghiêm trọng hơn C1/C2 nhưng làm drag-reorder (dnd-kit, Phase 4/5) không ổn định.
- **Đề xuất:** cân nhắc unique, nhưng lưu ý kỹ thuật reorder swap dễ va đập unique giữa chừng.
```sql
-- Tùy chọn; cần reorder kiểu gán lại toàn bộ position 0..n trong 1 transaction
ALTER TABLE content_media
  ADD CONSTRAINT uq_content_media_position UNIQUE (content_id, position)
  DEFERRABLE INITIALLY DEFERRED;
```
- **Đánh đổi:** `DEFERRABLE` cho phép swap trong transaction. Nếu thấy phức tạp, có thể bỏ và chỉ dựa tie-break `id`. Ưu tiên thấp-trung.

#### M3. Slug UNIQUE toàn cục thay vì unique theo type
- **Vị trí:** `content.py:24` `unique=True`; `unique_slug` (`slug.py`) kiểm tra trùng toàn cục.
- **Rủi ro thực tế:** không phải bug, nhưng giới hạn không gian URL. `/music/hello` và `/photos/hello` không thể cùng tồn tại — slug thứ hai bị auto thêm `-2` dù khác type. URL kém đẹp. Route public đã tách theo type (`public.py`) nên unique theo `(type, slug)` là tự nhiên hơn.
- **Đề xuất:**
```sql
-- Đổi từ unique toàn cục sang unique theo type
DROP INDEX ix_contents_slug;             -- index unique hiện tại
CREATE UNIQUE INDEX uq_contents_type_slug ON contents (type, slug);
-- (vẫn nên giữ 1 index thường trên slug nếu có truy vấn slug không kèm type)
```
- **Đánh đổi:** cần sửa `unique_slug` để kiểm tra theo `(type, slug)`. Đây là **quyết định thiết kế**: nếu muốn slug toàn cục để URL gọn không lộ type, giữ nguyên. Khuyến nghị đổi theo type, ưu tiên trung.

#### M4. Filter JSONB `body->>'category'/'artist'` không có index
- **Vị trí:** `_apply_filters` (`content_query.py:24-29`) lọc `Content.body[key].astext == value`; route music dùng category/artist (`public.py:62`).
- **Rủi ro thực tế:** filter này chạy kèm `type=music AND status=published`. Partial index C3 đã thu hẹp tập rất nhiều, nên `body->>'artist'=...` chỉ filter trên tập nhỏ — thường ổn. Chỉ thành vấn đề nếu music published rất lớn và lọc artist là route nóng riêng.
- **Đề xuất (chỉ khi đo thấy chậm):** expression index có điều kiện:
```sql
CREATE INDEX ix_contents_music_artist
  ON contents ((body->>'artist'))
  WHERE type='music' AND status='published';
```
- **Đánh đổi:** đừng làm sớm (over-engineer). Để dành tới khi có dữ liệu thật + đo. Ưu tiên thấp-trung.

#### M5. Thiếu index `author_id`
- **Vị trí:** FK `author_id` (`content.py:34`) không index (xác nhận `pg_indexes`).
- **Rủi ro thực tế:** (a) màn CMS "nội dung của tôi" lọc theo author sẽ seq-scan; (b) khi xóa user, `ON DELETE SET NULL` phải quét `contents` tìm tham chiếu — không index thì chậm ở quy mô lớn. Tác giả ít nên ưu tiên thấp-trung.
- **Đề xuất:**
```sql
CREATE INDEX ix_contents_author_id ON contents (author_id);
```

---

### THẤP / ĐỊNH HƯỚNG TƯƠNG LAI (đánh đổi thiết kế, không phải bug)

#### L1. Offset pagination → cân nhắc cursor (keyset)
- `content_query.py:56` dùng `OFFSET (page-1)*size`. Offset sâu (trang 50+) đắt dần vì DB vẫn quét rồi bỏ. Với partial index C3 (đã sort sẵn theo `published_at, id`), chuyển sang **keyset/cursor** (`WHERE (published_at,id) < (:last_pub,:last_id)`) gần như O(1) mỗi trang. Để dành Phase 8 (hiệu năng). Lưu ý: cursor không cho nhảy trang số — quyết định UX.

#### L2. Versioning/revision cho CMS
- Chưa có lịch sử bản nội dung. CMS (Phase 6/7) thường cần "khôi phục bản trước". `update_content` ghi đè trực tiếp (`content_admin.py:76-90`). Nếu cần: bảng `content_revisions(content_id, version, title, summary, body, created_at, created_by)` snapshot mỗi lần publish. Định hướng Phase 6+, không làm sớm.

#### L3. Audit `created_by` / `updated_by`
- Chỉ có `author_id`. Không biết ai sửa lần cuối (editor vs author). Cân nhắc thêm `updated_by` khi RBAC nhiều người cùng sửa. Ưu tiên thấp.

#### L4. Soft-delete
- `delete_content` xóa cứng (`content_admin.py:93-95`), cascade luôn `content_media`. Vòng đời đã có `archived` — đa phần dùng archived thay xóa là đủ, nên **không cần** soft-delete riêng. Ghi nhận để khỏi nhầm archived với delete.

#### L5. Media: chưa có hash dedup, chưa có bảng variants, chưa có owner
- (a) **Dedup:** thêm `media.checksum` (sha256) + UNIQUE để chặn upload trùng file. (b) **Variants:** Phase 5 sinh thumbnail/responsive — nên bảng riêng `media_variants(media_id, variant, storage_key, width, height)` thay vì nhồi vào `body`. (c) **Owner/uploaded_by** trên media để RBAC + dọn rác. Tất cả định hướng Phase 5, không làm bây giờ.
```sql
-- Phác thảo Phase 5
ALTER TABLE media ADD COLUMN checksum char(64);
CREATE UNIQUE INDEX uq_media_checksum ON media (checksum) WHERE checksum IS NOT NULL;
```

#### L6. Media orphan
- Xóa content cascade `content_media` nhưng `media` ở lại (đúng, vì media dùng chung). Cần job dọn media không còn link nào (Phase 5/9). Không phải bug.

#### L7. `media.size` là `INTEGER` (~2.1GB trần)
- `media.py:19` map `int` → `INTEGER`. Đủ cho ảnh, nhưng video lớn (>2GB) sẽ tràn. Nếu cho upload video lớn, đổi `BIGINT`. Ưu tiên thấp, tùy use-case.

#### L8. Đa ngôn ngữ
- Hiện một bản ghi một ngôn ngữ. Nếu sau này cần i18n: cột `locale` + unique `(type, slug, locale)`, hoặc bảng dịch riêng. Chưa trong lộ trình — chỉ ghi nhận.

---

## Lộ trình áp dụng đề xuất

**Đợt 1 — toàn vẹn dữ liệu (làm trước khi có nhiều dữ liệu thật, rẻ khi bảng còn rỗng):**
- C1 unique 1 primary/content
- C2 UNIQUE(content_id, media_id)
- C4 CHECK enum (type/status/role)
- M1 CHECK published ⇒ published_at NOT NULL (kèm sửa `set_status` ở ứng dụng)

**Đợt 2 — hiệu năng route public (trước/đúng Phase 4 MVP):**
- C3 partial index `(type, published_at DESC, id DESC) WHERE status='published'`
- M5 index `author_id`
- M2 cân nhắc UNIQUE(content_id, position) DEFERRABLE (nếu drag-reorder cần)

**Đợt 3 — quyết định thiết kế (cân nhắc, có thể hoãn):**
- M3 slug unique theo type (sửa kèm `unique_slug`)
- M4 expression index JSONB (chỉ khi đo thấy chậm)

**Đợt 4 — định hướng phase sau (không làm sớm):**
- L1 cursor pagination (Phase 8) · L2 versioning (Phase 6) · L5 media variants/dedup/owner (Phase 5) · L6 job dọn orphan · L7 size BIGINT nếu video lớn

> Mọi đề xuất DDL trên là PHÁC THẢO để team tự tạo migration Alembic. Lần review này không tạo/chạy migration.
