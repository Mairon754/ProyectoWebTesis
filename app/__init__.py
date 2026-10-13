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


    @app.cli.command("quality-scan")
    @click.option(
        "--scope",
        type=click.Choice(["completed", "all"], case_sensitive=False),
        default="completed",
        show_default=True,
    )
    def quality_scan_command(scope: str) -> None:
        """Ejecuta el protocolo automático vigente sobre sesiones existentes."""

        from .services.dataset_service import get_research_sessions
        from .services.quality_service import run_automatic_quality_check

        sessions = get_research_sessions(
            {},
            completed_only=scope.lower() == "completed",
        )
        passed = 0
        blocked = 0
        warnings = 0
        for assessment in sessions:
            check = run_automatic_quality_check(assessment)
            passed += check.status == "passed"
            blocked += check.status == "blocked"
            warnings += check.warning_count

        click.echo(f"protocol: DATA_QC_V1_STRUCTURAL_COMPLETENESS")
        click.echo(f"sessions_scanned: {len(sessions)}")
        click.echo(f"passed: {passed}")
        click.echo(f"blocked: {blocked}")
        click.echo(f"warnings: {warnings}")

    @app.cli.command("dataset-freeze")
    @click.option("--version", required=True)
    @click.option(
        "--collection-phase",
        required=True,
        type=click.Choice(["pilot", "final"], case_sensitive=False),
    )
    @click.option("--train-ratio", required=True, type=str)
    @click.option("--validation-ratio", required=True, type=str)
    @click.option("--test-ratio", required=True, type=str)
    def dataset_freeze_command(
        version: str,
        collection_phase: str,
        train_ratio: str,
        validation_ratio: str,
        test_ratio: str,
    ) -> None:
        """Congela un release científico con splits explícitos."""

        from .services.dataset_release_service import (
            DatasetReleaseError,
            freeze_dataset_release,
            release_manifest,
        )

        try:
            release = freeze_dataset_release(
                version=version,
                collection_phase=collection_phase.lower(),
                train_ratio=train_ratio,
                validation_ratio=validation_ratio,
                test_ratio=test_ratio,
            )
            manifest = release_manifest(release)
        except DatasetReleaseError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:
            app.logger.exception("Falló la congelación del dataset.")
            raise click.ClickException(
                "No fue posible congelar el release científico."
            ) from exc

        click.echo(f"release: {manifest['version']}")
        click.echo(f"phase: {manifest['collection_phase']}")
        click.echo(f"records: {manifest['record_count']}")
        click.echo(f"splits: {manifest['split_counts']}")
        click.echo(f"release_hash_sha256: {manifest['release_hash_sha256']}")

    @app.cli.command("dataset-manifest")
    @click.option("--version", required=True)
    def dataset_manifest_command(version: str) -> None:
        """Imprime en JSON el manifiesto verificable de un release."""

        import json

        from .services.dataset_release_service import (
            DatasetReleaseError,
            get_dataset_release,
            release_manifest,
        )

        try:
            manifest = release_manifest(get_dataset_release(version))
        except DatasetReleaseError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(json.dumps(manifest, ensure_ascii=False, indent=2))

    @app.cli.command("dataset-package")
    @click.option("--version", required=True)
    def dataset_package_command(version: str) -> None:
        """Genera paquete local CSV+JSON bajo exports/dataset_releases/."""

        import json
        from pathlib import Path

        from .services.dataset_release_service import (
            DatasetReleaseError,
            dataset_dictionary,
            export_release_records,
            get_dataset_release,
            release_manifest,
        )
        from .services.dataset_service import export_records_to_csv

        try:
            release = get_dataset_release(version)
            manifest = release_manifest(release)
            dictionary = dataset_dictionary()
        except DatasetReleaseError as exc:
            raise click.ClickException(str(exc)) from exc

        output_dir = (
            Path(app.root_path).parent
            / "exports"
            / "dataset_releases"
            / release.version
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "data_dictionary.json").write_text(
            json.dumps(dictionary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        all_rows = export_release_records(release)
        (output_dir / "all.csv").write_text(
            export_records_to_csv(all_rows),
            encoding="utf-8-sig",
        )
        (output_dir / "all.json").write_text(
            json.dumps(all_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for split_name in ("train", "validation", "test"):
            rows = export_release_records(release, split_name=split_name)
            (output_dir / f"{split_name}.csv").write_text(
                export_records_to_csv(rows),
                encoding="utf-8-sig",
            )
            (output_dir / f"{split_name}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        click.echo(f"Paquete generado en: {output_dir}")
        click.echo(f"release_hash_sha256: {release.release_hash_sha256}")

    @app.cli.command("repro-status")
    def repro_status_command() -> None:
        """Muestra el entorno reproducible sin imprimir secretos."""

        import json

        from .services.experiment_service import (
            _requirements_hash,
            code_state,
            runtime_environment,
        )

        payload = {
            "code": code_state(),
            "requirements_sha256": _requirements_hash(),
            "environment": runtime_environment(),
        }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    @app.cli.command("experiment-register")
    @click.option("--run-code", required=True)
    @click.option("--dataset-version", required=True)
    @click.option("--model-name", required=True)
    @click.option("--model-version", required=True)
    @click.option(
        "--run-type",
        required=True,
        type=click.Choice(
            ["training", "inference", "evaluation"],
            case_sensitive=False,
        ),
    )
    @click.option("--seed", type=int, default=None)
    @click.option(
        "--hyperparameters-json",
        required=True,
        help="Objeto JSON sin secretos.",
    )
    @click.option(
        "--conditions-json",
        required=True,
        help="Objeto JSON con condiciones controladas de ejecución.",
    )
    def experiment_register_command(
        run_code: str,
        dataset_version: str,
        model_name: str,
        model_version: str,
        run_type: str,
        seed: int | None,
        hyperparameters_json: str,
        conditions_json: str,
    ) -> None:
        """Registra el manifiesto reproducible antes de una ejecución."""

        import json

        from .services.experiment_service import (
            ExperimentRunError,
            experiment_manifest,
            register_experiment_run,
        )

        try:
            hyperparameters = json.loads(hyperparameters_json)
            conditions = json.loads(conditions_json)
        except json.JSONDecodeError as exc:
            raise click.ClickException(
                "Los campos JSON deben contener objetos JSON válidos."
            ) from exc
        if not isinstance(hyperparameters, dict) or not isinstance(conditions, dict):
            raise click.ClickException(
                "--hyperparameters-json y --conditions-json deben ser objetos JSON."
            )

        try:
            run = register_experiment_run(
                run_code=run_code,
                dataset_version=dataset_version,
                model_name=model_name,
                model_version=model_version,
                run_type=run_type.lower(),
                seed=seed,
                hyperparameters=hyperparameters,
                conditions=conditions,
            )
        except ExperimentRunError as exc:
            raise click.ClickException(str(exc)) from exc

        manifest = experiment_manifest(run)
        click.echo(f"run_code: {manifest['run_code']}")
        click.echo(f"dataset_version: {manifest['dataset_version']}")
        click.echo(
            f"dataset_release_hash_sha256: "
            f"{manifest['dataset_release_hash_sha256']}"
        )
        click.echo(f"code_commit_sha: {manifest['code_commit_sha']}")
        click.echo(f"git_dirty: {manifest['git_dirty']}")
        click.echo(
            f"manifest_hash_sha256: {manifest['manifest_hash_sha256']}"
        )

    @app.cli.command("experiment-complete")
    @click.option("--run-code", required=True)
    @click.option("--metrics-json", required=True)
    def experiment_complete_command(
        run_code: str,
        metrics_json: str,
    ) -> None:
        """Cierra una ejecución y conserva sus métricas como JSON."""

        import json

        from .services.experiment_service import (
            ExperimentRunError,
            complete_experiment_run,
        )

        try:
            metrics = json.loads(metrics_json)
        except json.JSONDecodeError as exc:
            raise click.ClickException("--metrics-json no es JSON válido.") from exc
        if not isinstance(metrics, dict):
            raise click.ClickException("--metrics-json debe ser un objeto JSON.")

        try:
            run = complete_experiment_run(run_code, metrics=metrics)
        except ExperimentRunError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(f"run_code: {run.run_code}")
        click.echo(f"status: {run.status}")

    @app.cli.command("experiment-fail")
    @click.option("--run-code", required=True)
    @click.option("--reason", required=True)
    def experiment_fail_command(run_code: str, reason: str) -> None:
        """Cierra una ejecución fallida sin almacenar trazas sensibles."""

        from .services.experiment_service import (
            ExperimentRunError,
            fail_experiment_run,
        )

        try:
            run = fail_experiment_run(run_code, reason=reason)
        except ExperimentRunError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(f"run_code: {run.run_code}")
        click.echo(f"status: {run.status}")

    @app.cli.command("experiment-manifest")
    @click.option("--run-code", required=True)
    def experiment_manifest_command(run_code: str) -> None:
        """Imprime el manifiesto reproducible de una ejecución."""

        import json

        from .services.experiment_service import (
            ExperimentRunError,
            experiment_manifest,
            get_experiment_run,
        )

        try:
            manifest = experiment_manifest(get_experiment_run(run_code))
        except ExperimentRunError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(json.dumps(manifest, ensure_ascii=False, indent=2))

    @app.cli.command("privacy-purge-participant")
    @click.option("--participant-code", required=True)
    @click.option(
        "--confirm",
        required=True,
        help="Debe repetir exactamente el código del participante.",
    )
    def privacy_purge_participant_command(
        participant_code: str,
        confirm: str,
    ) -> None:
        """Elimina de la base activa los datos ligados a un participante."""

        normalized = participant_code.strip().upper()
        if confirm.strip().upper() != normalized:
            raise click.ClickException(
                "--confirm debe coincidir exactamente con --participant-code."
            )

        from .services.assessment_service import (
            AssessmentServiceError,
            purge_participant_data,
        )

        try:
            result = purge_participant_data(normalized)
        except AssessmentServiceError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:
            app.logger.exception("Falló la eliminación controlada de participante.")
            raise click.ClickException(
                "No fue posible eliminar los datos del participante."
            ) from exc

        click.echo(
            "Datos eliminados de la base activa para "
            f"{result['participant_code']}."
        )
        click.echo(
            "Sesiones eliminadas: "
            f"{result['assessment_sessions_deleted']}"
        )
        click.echo(
            "Consentimientos eliminados: "
            f"{result['consent_records_deleted']}"
        )
        click.echo(
            "IMPORTANTE: revisar también backups/snapshots según el "
            "procedimiento institucional de retención."
        )


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
