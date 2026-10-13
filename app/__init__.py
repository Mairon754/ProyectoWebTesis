"""Fábrica de la aplicación Flask para la plataforma RIASEC."""

from __future__ import annotations

import os

import click
from flask import Flask, jsonify, request

from config import CONFIG_BY_NAME, validate_config

from .extensions import db, migrate


def _register_blueprints(app: Flask) -> None:
    """Registra los módulos HTTP de la plataforma."""

    from .routes.api import api_bp
    from .routes.assessment import assessment_bp
    from .routes.main import main_bp
    from .routes.results import results_bp
    from .routes.research import research_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(research_bp)


def _register_cli_commands(app: Flask) -> None:
    """Registra comandos administrativos explícitos y seguros."""

    @app.cli.command("seed-catalogs")
    def seed_catalogs_command() -> None:
        """Carga catálogos maestros sin duplicar registros existentes."""

        from .services.catalog_service import CatalogSeedError, seed_catalogs

        try:
            summary = seed_catalogs()
        except CatalogSeedError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:
            app.logger.exception("Falló la carga de catálogos.")
            raise click.ClickException(
                "No fue posible cargar los catálogos. Revisa PostgreSQL y logs."
            ) from exc

        created = sum(summary.values())
        click.echo("Catálogos RIASEC verificados correctamente.")
        click.echo(f"Registros nuevos creados: {created}")
        for key, value in summary.items():
            click.echo(f"  {key}: {value}")

    @app.cli.command("catalog-status")
    def catalog_status_command() -> None:
        """Muestra si los catálogos mínimos están listos para evaluar."""

        from .services.catalog_service import get_catalog_status

        try:
            status = get_catalog_status()
        except Exception as exc:
            app.logger.exception("No fue posible consultar catálogos.")
            raise click.ClickException(
                "No fue posible consultar el estado de los catálogos."
            ) from exc

        click.echo(f"ready: {status['ready']}")
        for key, value in status["counts"].items():
            expected = status["expected_minimum"][key]
            click.echo(f"  {key}: {value}/{expected}")
        click.echo(
            "instrument_verification_status: "
            f"{status['instrument_verification_status']}"
        )

    @app.cli.command("scientific-status")
    def scientific_status_command() -> None:
        """Muestra trazabilidad científica del instrumento RIASEC local."""

        from .services.catalog_service import get_catalog_status
        from .services.riasec_protocol import (
            SCORING_SPEC_SHA256,
            SCORING_VERSION,
            TARGET_PROTOCOL_VERSION,
        )

        try:
            status = get_catalog_status()
        except Exception as exc:
            app.logger.exception("No fue posible consultar estado científico.")
            raise click.ClickException(
                "No fue posible consultar el estado científico RIASEC."
            ) from exc

        click.echo(
            "instrument_verification_status: "
            f"{status['instrument_verification_status']}"
        )
        click.echo(
            "source_verification_status: "
            f"{status['source_verification_status']}"
        )
        click.echo(
            "instrument_source_hash_sha256: "
            f"{status['instrument_source_hash_sha256']}"
        )
        click.echo(
            "instrument_local_content_hash_sha256: "
            f"{status['instrument_local_content_hash_sha256']}"
        )
        click.echo(f"scoring_version: {SCORING_VERSION}")
        click.echo(f"scoring_spec_sha256: {SCORING_SPEC_SHA256}")
        click.echo(f"target_protocol_version: {TARGET_PROTOCOL_VERSION}")


def _register_security_headers(app: Flask) -> None:
    """Aplica una línea base de cabeceras de seguridad."""

    sensitive_prefixes = (
        "/assessment",
        "/results",
        "/investigacion",
        "/api/",
        "/consent",
        "/demographics",
    )

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )

        if request.path.startswith(sensitive_prefixes):
            response.headers.setdefault("Cache-Control", "no-store, private")
            response.headers.setdefault("Pragma", "no-cache")

        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


def _register_error_handlers(app: Flask) -> None:
    """Devuelve errores JSON consistentes para rutas bajo /api/."""

    def api_error(message: str, status_code: int):
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": message,
                }
            ),
            status_code,
        )

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return api_error("Recurso API no encontrado.", 404)
        return error

    @app.errorhandler(405)
    def method_not_allowed(error):
        if request.path.startswith("/api/"):
            return api_error("Método HTTP no permitido para este recurso.", 405)
        return error

    @app.errorhandler(500)
    def internal_server_error(error):
        if request.path.startswith("/api/"):
            app.logger.exception("Error interno no controlado en la API.")
            return api_error("Ocurrió un error interno inesperado.", 500)
        return error


def create_app(config_name: str | None = None) -> Flask:
    """Construye y configura una instancia de Flask."""

    selected_config = (
        config_name or os.getenv("APP_ENV", "development")
    ).strip().lower()

    config_class = CONFIG_BY_NAME.get(selected_config)
    if config_class is None:
        allowed = ", ".join(sorted(CONFIG_BY_NAME))
        raise RuntimeError(
            f"APP_ENV='{selected_config}' no es válido. "
            f"Valores permitidos: {allowed}."
        )

    validate_config(selected_config, config_class)

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from . import models  # noqa: F401, PLC0415

    migrate.init_app(app, db)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_security_headers(app)
    _register_cli_commands(app)

    app.logger.info(
        "Aplicación RIASEC inicializada en entorno '%s'.",
        selected_config,
    )

    return app
