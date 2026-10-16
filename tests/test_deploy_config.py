"""Cấu hình deploy giữ bí mật và các giá trị hiện có trên server."""

from unittest.mock import Mock

import pytest

from scripts import deploy


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for key in (
        "DEPLOY_GOOGLE_DRIVE_API_KEY",
        "DEPLOY_JWT_SECRET",
        "DEPLOY_PUBLIC_SITE_URL",
        "DEPLOY_GOOGLE_DRIVE_FOLDER_ID",
        "DEPLOY_DATABASE_URL",
        "GOOGLE_DRIVE_API_KEY",
        "JWT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DEPLOY_GOOGLE_DRIVE_API_KEY", "test-drive-credential")
    monkeypatch.setenv("DEPLOY_JWT_SECRET", "test-production-jwt-" + "a" * 40)
    path = tmp_path / ".env"
    path.write_text(
        "# preserve server settings\n"
        "DATABASE_URL=postgresql+asyncpg://existing:password@db.example/test\n"
        "JWT_SECRET=weak\n"
        "PUBLIC_CONTENT_SOURCE=database\n"
        "SUPABASE_SERVICE_KEY=keep-storage-credential\n"
        'CORS_ORIGINS=["https://existing.example"]\n',
        encoding="utf-8",
    )
    return path


def test_configure_preserves_database_and_backs_up_old_environment(
    environment, monkeypatch, capsys
):
    before = environment.read_bytes()
    monkeypatch.setenv("DEPLOY_PUBLIC_SITE_URL", "https://production.example/")
    deploy.configure(environment)
    current = deploy.settings_from_env(environment)
    assert current.is_prod
    assert current.public_content_source == "drive"
    assert current.google_drive_api_key == "test-drive-credential"
    assert current.jwt_secret == "test-production-jwt-" + "a" * 40
    assert current.supabase_service_key == "keep-storage-credential"
    assert (
        current.database_url == "postgresql+asyncpg://existing:password@db.example/test"
    )
    assert current.cors_origins == [
        "https://existing.example",
        "https://production.example",
    ]
    backups = list(
        environment.parent.glob(".local/deploy-backups/*/environment.backup")
    )
    assert len(backups) == 1
    assert backups[0].read_bytes() == before
    output = capsys.readouterr().out
    assert current.google_drive_api_key not in output
    assert current.jwt_secret not in output
    assert current.database_url not in output


def test_existing_strong_jwt_is_preserved(environment):
    original = "existing-production-jwt-" + "z" * 40
    environment.write_text(
        environment.read_text().replace("JWT_SECRET=weak", f"JWT_SECRET={original}")
    )
    deploy.configure(environment)
    assert deploy.settings_from_env(environment).jwt_secret == original


def test_database_secret_updates_only_database_and_keeps_private_backup(
    environment, monkeypatch, capsys
):
    before = environment.read_bytes()
    database = "postgresql+asyncpg://postgres.project:new-password@pooler.example:6543/postgres"
    monkeypatch.setenv("DEPLOY_DATABASE_URL", database)
    deploy.configure(environment)
    settings = deploy.settings_from_env(environment)
    assert settings.database_url == database
    assert settings.supabase_service_key == "keep-storage-credential"
    backups = list(
        environment.parent.glob(".local/deploy-backups/*/environment.backup")
    )
    assert backups[0].read_bytes() == before
    assert database not in capsys.readouterr().out


@pytest.mark.parametrize("invalid", ["missing_key", "invalid_origin"])
def test_bad_configuration_leaves_server_environment_unchanged(
    environment, monkeypatch, invalid
):
    before = environment.read_bytes()
    if invalid == "missing_key":
        monkeypatch.delenv("DEPLOY_GOOGLE_DRIVE_API_KEY")
    else:
        monkeypatch.setenv(
            "DEPLOY_PUBLIC_SITE_URL", "https://user:password@site.example/"
        )
    with pytest.raises(ValueError):
        deploy.configure(environment)
    assert environment.read_bytes() == before
    assert not list(
        environment.parent.glob(".local/deploy-backups/*/environment.backup")
    )


def test_restart_passes_configuration_as_environment_not_arguments(
    environment, monkeypatch
):
    deploy.configure(environment)
    run = Mock()
    monkeypatch.setattr(deploy.subprocess, "run", run)
    monkeypatch.setenv("PUBLIC_CONTENT_SOURCE", "database")
    monkeypatch.setenv("JWT_SECRET", "stale-runner-value")
    monkeypatch.setenv("ACTIONS_RUNTIME_TOKEN", "temporary-actions-token")
    deploy.restart(environment)
    args, kwargs = run.call_args
    assert args[0][0] == "pm2"
    assert args[0][-1] == "--update-env"
    assert kwargs["env"]["PUBLIC_CONTENT_SOURCE"] == "drive"
    assert kwargs["env"]["RUNNER_TRACKING_ID"] == ""
    assert kwargs["env"]["JWT_SECRET"] == "test-production-jwt-" + "a" * 40
    assert "DEPLOY_JWT_SECRET" not in kwargs["env"]
    assert "ACTIONS_RUNTIME_TOKEN" not in kwargs["env"]
    assert "test-drive-credential" not in repr(args)
    assert kwargs["check"] is True


def test_migration_uses_deployment_file_instead_of_stale_runner_database(
    environment, monkeypatch
):
    deploy.configure(environment)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://old:wrong@invalid-host/db")
    run = Mock()
    monkeypatch.setattr(deploy.subprocess, "run", run)
    deploy.migrate(environment)
    args, kwargs = run.call_args
    assert args[0][-4:] == ["-m", "alembic", "upgrade", "head"]
    assert kwargs["env"]["DATABASE_URL"] == (
        "postgresql+asyncpg://existing:password@db.example/test"
    )
    assert "existing:password" not in repr(args)
