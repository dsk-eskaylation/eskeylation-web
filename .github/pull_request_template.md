## Mô tả

<!-- Thay đổi gì và vì sao -->

## Phase / Story

<!-- Ví dụ: Phase 2 — Public API (Story 9.1, 3.4) -->

## Checklist

- [ ] `uv run ruff check .` và `uv run ruff format --check .` xanh
- [ ] `uv run pytest` xanh (kèm test cho thay đổi mới)
- [ ] Có migration Alembic nếu đổi schema (đã chạy `alembic upgrade head`)
- [ ] Không commit secrets (`.env`)
- [ ] Tự review diff: mỗi dòng đổi đều phục vụ mục tiêu PR
