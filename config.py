"""Configuración central de la aplicación RIASEC.

FASE 1 — Línea base de seguridad
--------------------------------
Los secretos se obtienen exclusivamente del entorno o de un archivo .env
LOCAL no versionado. El repositorio solo contiene .env.example.

La misma base de código puede ejecutarse en development, testing y production.
Producción activa cookies seguras y validaciones adicionales para impedir el
arranque con credenciales débiles o de ejemplo.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

# .env es únicamente una comodidad de desarrollo local. Las variables ya
# definidas por el sistema operativo siempre tienen prioridad.
load_dotenv(BASE_DIR / ".env", override=False)


class BaseConfig:
    """Configuración compartida por todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_NAME = "riasec_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # La plataforma no necesita cuerpos HTTP grandes durante la evaluación.
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    RESEARCHER_ACCOUNTS = [
        {
            "username": os.getenv("RESEARCHER_1_USERNAME", "investigador_1"),
            "display_name": os.getenv(
                "RESEARCHER_1_NAME",
                "Investigador 1",
            ),
            "password_hash": os.getenv("RESEARCHER_1_PASSWORD_HASH", ""),
        },
        {
            "username": os.getenv("RESEARCHER_2_USERNAME", "investigador_2"),
            "display_name": os.getenv(
                "RESEARCHER_2_NAME",
                "Investigador 2",
            ),
            "password_hash": os.getenv("RESEARCHER_2_PASSWORD_HASH", ""),
        },
    ]

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }


class DevelopmentConfig(BaseConfig):
    """Configuración para desarrollo local."""

    DEBUG = True
    TESTING = False


class TestingConfig(BaseConfig):
    """Configuración exclusiva para pruebas automatizadas."""

    DEBUG = False
    TESTING = True

    # Nunca usamos DATABASE_URL como fallback: los tests crean/eliminan tablas
    # y deben ejecutarse únicamente contra una base PostgreSQL de pruebas.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "")


class ProductionConfig(BaseConfig):
    """Configuración endurecida para despliegue en producción."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def _contains_placeholder(value: str) -> bool:
    upper = value.upper()
    markers = (
        "CHANGE_ME",
        "CAMBIAR",
        "PASSWORD",
        "SECRET_KEY_HERE",
        "EXAMPLE",
    )
    return any(marker in upper for marker in markers)


def validate_config(config_name: str, config_class: type[BaseConfig]) -> None:
    """Valida variables esenciales antes de inicializar Flask."""

    if not config_class.SECRET_KEY:
        raise RuntimeError(
            "Falta SECRET_KEY. Defínela como variable de entorno o en un .env local."
        )

    if not config_class.SQLALCHEMY_DATABASE_URI:
        variable = "TEST_DATABASE_URL" if config_name == "testing" else "DATABASE_URL"
        raise RuntimeError(
            f"Falta {variable}. Defínela como variable de entorno o en un .env local."
        )

    if config_name != "production":
        return

    secret = str(config_class.SECRET_KEY)
    database_uri = str(config_class.SQLALCHEMY_DATABASE_URI)

    if len(secret) < 32 or _contains_placeholder(secret):
        raise RuntimeError(
            "SECRET_KEY de producción debe ser aleatoria, no reutilizada y tener "
            "al menos 32 caracteres."
        )

    if _contains_placeholder(database_uri):
        raise RuntimeError(
            "DATABASE_URL de producción contiene un valor de ejemplo."
        )

    if not database_uri.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "Producción debe utilizar una DATABASE_URL de PostgreSQL."
        )

    configured_accounts = [
        account
        for account in config_class.RESEARCHER_ACCOUNTS
        if str(account.get("username", "")).strip()
        and str(account.get("password_hash", "")).strip()
        and not _contains_placeholder(str(account.get("password_hash", "")))
    ]
    if not configured_accounts:
        raise RuntimeError(
            "Producción requiere al menos una cuenta investigadora con hash "
            "de contraseña configurado."
        )
