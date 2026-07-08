# ---- Stage 1: build React SPA ----
FROM node:22-alpine AS spa
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: FastAPI + uv ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /srv

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    ENVIRONMENT=prod

# Cài dependency theo đúng lockfile (layer cache tốt: chỉ rebuild khi lock đổi)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
# SPA build từ stage 1 -> app.main tự phát hiện frontend/dist và serve same-origin
COPY --from=spa /build/dist frontend/dist

EXPOSE 8000
# Secrets (DATABASE_URL, JWT_SECRET, SUPABASE_*) truyền qua biến môi trường khi run.
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
