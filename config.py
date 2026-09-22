"""Configuración central de la aplicación RIASEC.

FASE 1 — Arquitectura
---------------------
Este módulo concentra la configuración por entorno. No contiene lógica de
negocio ni credenciales reales. Los valores sensibles se leen desde `.env`.

La separación por entornos permite que el mismo código se ejecute en
`development`, `testing` y `production` sin modificar archivos fuente.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

# Cargamos únicamente el archivo .env ubicado en la raíz del proyecto.
# python-dotenv no sobrescribe variables ya definidas por el sistema operativo,
# por lo que en producción las variables del servidor tienen prioridad.
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Configuración compartida por todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Fase 14: dos cuentas privadas sin almacenar contraseñas en el código.
    # Los hashes se generan con werkzeug.security.generate_password_hash.
    RESEARCHER_ACCOUNTS = [
        {
            "username": os.getenv("RESEARCHER_1_USERNAME", "mairon"),
            "display_name": os.getenv(
                "RESEARCHER_1_NAME",
                "Mairon Andres Cuabu",
            ),
            "password_hash": os.getenv("RESEARCHER_1_PASSWORD_HASH", ""),
        },
        {
            "username": os.getenv("RESEARCHER_2_USERNAME", "frank"),
            "display_name": os.getenv(
                "RESEARCHER_2_NAME",
                "Frank Manuell Cortes Carreño",
            ),
            "password_hash": os.getenv("RESEARCHER_2_PASSWORD_HASH", ""),
        },
    ]

    # `pool_pre_ping` comprueba conexiones antes de reutilizarlas. Esto ayuda a
    # recuperarse de conexiones PostgreSQL cerradas por inactividad.
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
    """Configuración segura para despliegue en producción."""

    DEBUG = False
    TESTING = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def validate_config(config_name: str, config_class: type[BaseConfig]) -> None:
    """Valida variables esenciales antes de inicializar Flask.

    Args:
        config_name: Nombre lógico del entorno seleccionado.
        config_class: Clase de configuración que será cargada por Flask.

    Raises:
        RuntimeError: Si falta una variable indispensable o si producción usa
        valores de ejemplo inseguros.
    """

    if not config_class.SECRET_KEY:
        raise RuntimeError(
            "Falta SECRET_KEY. Defínela en .env o como variable de entorno."
        )

    if not config_class.SQLALCHEMY_DATABASE_URI:
        variable = "TEST_DATABASE_URL" if config_name == "testing" else "DATABASE_URL"
        raise RuntimeError(
            f"Falta {variable}. Defínela en .env o como variable de entorno."
        )

    if config_name == "production":
        secret_upper = config_class.SECRET_KEY.upper()
        database_upper = config_class.SQLALCHEMY_DATABASE_URI.upper()

        if "CHANGE_ME" in secret_upper or "CAMBIAR" in secret_upper:
            raise RuntimeError(
                "SECRET_KEY contiene un valor de ejemplo. Configura una clave "
                "segura antes de iniciar en producción."
            )

        if "CHANGE_ME" in database_upper or "CAMBIAR" in database_upper:
            raise RuntimeError(
                "DATABASE_URL contiene credenciales de ejemplo. Configura la "
                "conexión real antes de iniciar en producción."
            )
