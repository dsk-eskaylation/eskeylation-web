from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401 — đăng ký toàn bộ model
from app.db import Base


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert {"users", "contents", "media", "content_media"} <= tables


def test_content_media_is_association_with_attributes():
    cm = Base.metadata.tables["content_media"]
    # M-N CÓ thuộc tính: phải có caption, position, is_primary + 2 FK
    assert {"caption", "position", "is_primary"} <= set(cm.columns.keys())
    fks = {fk.column.table.name for fk in cm.foreign_keys}
    assert fks == {"contents", "media"}


def test_postgres_ddl_compiles():
    # JSONB / enum là PG-specific — đảm bảo compile được cho dialect Postgres.
    ddl = str(
        CreateTable(Base.metadata.tables["contents"]).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "JSONB" in ddl
