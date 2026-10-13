"""Pruebas de la línea base de seguridad de configuración."""

from __future__ import annotations

import pytest

from config import ProductionConfig, TestingConfig, validate_config


def _valid_researcher_account() -> list[dict[str, str]]:
    return [
        {
            "username": "investigador",
            "display_name": "Investigador",
            "password_hash": "scrypt:32768:8:1$hash-de-prueba-no-placeholder",
        }
    ]


def test_production_rejects_short_secret(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "demasiado-corta")
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg://user:pass@db/riasec",
    )
    monkeypatch.setattr(
        ProductionConfig,
        "RESEARCHER_ACCOUNTS",
        _valid_researcher_account(),
    )

    with pytest.raises(RuntimeError, match="al menos 32 caracteres"):
        validate_config("production", ProductionConfig)


def test_production_requires_postgresql(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///riasec.db",
    )
    monkeypatch.setattr(
        ProductionConfig,
        "RESEARCHER_ACCOUNTS",
        _valid_researcher_account(),
    )

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        validate_config("production", ProductionConfig)


def test_production_cookie_baseline_is_secure():
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProductionConfig.SESSION_COOKIE_SAMESITE == "Lax"


def test_sensitive_pages_receive_security_headers(monkeypatch):
    monkeypatch.setattr(TestingConfig, "SECRET_KEY", "pytest-security-secret")
    monkeypatch.setattr(
        TestingConfig,
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///:memory:",
    )

    from app import create_app

    app = create_app("testing")
    response = app.test_client().get("/consent")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store, private"
