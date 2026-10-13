"""Registro seguro y reproducible de ejecuciones experimentales.

FASE 7 — Reproducibilidad y seguridad investigadora
----------------------------------------------------
El manifiesto captura dataset, modelo, semilla, hiperparámetros, condiciones,
entorno y estado del código sin copiar variables de entorno ni credenciales.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models import DatasetRelease, ExperimentRun


EXPERIMENT_PROTOCOL_VERSION = "EXPERIMENT_RUN_MANIFEST_V1"
SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "database_url",
    "private_key",
)


class ExperimentRunError(ValueError):
    """Error de contrato al registrar una ejecución."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def _assert_no_sensitive_keys(value: Any, path: str = "root") -> None:
    """Impide almacenar secretos por error dentro del manifiesto."""

    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(marker in normalized for marker in SENSITIVE_KEY_MARKERS):
                raise ExperimentRunError(
                    f"No se permite registrar una clave sensible en {path}.{key}."
                )
            _assert_no_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sensitive_keys(child, f"{path}[{index}]")


def _package_snapshot() -> dict[str, str]:
    """Captura versiones instaladas sin consultar internet."""

    packages: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if name and version:
            packages[str(name)] = str(version)
    return dict(sorted(packages.items(), key=lambda item: item[0].lower()))


def _requirements_hash() -> str | None:
    root = Path(__file__).resolve().parents[2]
    requirements = root / "requirements.txt"
    if not requirements.exists():
        return None
    return hashlib.sha256(requirements.read_bytes()).hexdigest()


def _git_output(*args: str) -> str | None:
    root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def code_state() -> dict[str, Any]:
    """Estado local de Git; no falla si Git no está disponible."""

    commit = _git_output("rev-parse", "HEAD")
    branch = _git_output("rev-parse", "--abbrev-ref", "HEAD")
    status = _git_output("status", "--porcelain")
    return {
        "commit_sha": commit,
        "branch": branch,
        "dirty": bool(status),
    }


def runtime_environment() -> dict[str, Any]:
    """Metadatos técnicos seguros; nunca serializa os.environ."""

    packages = _package_snapshot()
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "executable_name": Path(sys.executable).name,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "packages": packages,
    }


def _validate_run_code(value: str) -> str:
    normalized = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", normalized):
        raise ExperimentRunError(
            "run_code solo admite letras, números, punto, guion y guion bajo."
        )
    return normalized


def _require_text(value: Any, field_name: str, max_length: int = 120) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ExperimentRunError(f"{field_name} es obligatorio.")
    if len(normalized) > max_length:
        raise ExperimentRunError(
            f"{field_name} supera el máximo de {max_length} caracteres."
        )
    return normalized


def register_experiment_run(
    *,
    run_code: str,
    dataset_version: str,
    model_name: str,
    model_version: str,
    run_type: str,
    seed: int | None,
    hyperparameters: dict[str, Any],
    conditions: dict[str, Any],
) -> ExperimentRun:
    """Congela el manifiesto previo a entrenamiento/inferencia/evaluación."""

    normalized_code = _validate_run_code(run_code)
    normalized_type = str(run_type).strip().lower()
    if normalized_type not in {"training", "inference", "evaluation"}:
        raise ExperimentRunError(
            "run_type debe ser training, inference o evaluation."
        )
    _assert_no_sensitive_keys(hyperparameters, "hyperparameters")
    _assert_no_sensitive_keys(conditions, "conditions")

    existing = db.session.execute(
        select(ExperimentRun.id).where(ExperimentRun.run_code == normalized_code)
    ).scalar_one_or_none()
    if existing is not None:
        raise ExperimentRunError("Ya existe una ejecución con ese run_code.")

    release = db.session.execute(
        select(DatasetRelease).where(
            DatasetRelease.version == str(dataset_version).strip()
        )
    ).scalar_one_or_none()
    if release is None:
        raise ExperimentRunError("No existe el dataset release solicitado.")
    if release.status != "frozen":
        raise ExperimentRunError("El dataset release debe estar congelado.")

    environment = runtime_environment()
    package_hash = _sha256_json(environment["packages"])
    requirements_hash = _requirements_hash()
    git = code_state()
    manifest = {
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "run_code": normalized_code,
        "dataset": {
            "version": release.version,
            "release_hash_sha256": release.release_hash_sha256,
            "schema_hash_sha256": release.schema_hash_sha256,
            "target_protocol_version": release.target_protocol_version,
            "split_protocol_version": release.split_protocol_version,
        },
        "model": {
            "name": _require_text(model_name, "model_name"),
            "version": _require_text(model_version, "model_version"),
        },
        "run_type": normalized_type,
        "seed": seed,
        "hyperparameters": hyperparameters,
        "conditions": conditions,
        "environment": environment,
        "requirements_sha256": requirements_hash,
        "package_snapshot_sha256": package_hash,
        "code": git,
    }
    manifest_hash = _sha256_json(manifest)

    run = ExperimentRun(
        run_code=normalized_code,
        protocol_version=EXPERIMENT_PROTOCOL_VERSION,
        dataset_release_id=release.id,
        dataset_version=release.version,
        dataset_release_hash_sha256=release.release_hash_sha256,
        model_name=manifest["model"]["name"],
        model_version=manifest["model"]["version"],
        run_type=normalized_type,
        seed=seed,
        hyperparameters_json=hyperparameters,
        conditions_json=conditions,
        environment_json=environment,
        requirements_sha256=requirements_hash,
        package_snapshot_sha256=package_hash,
        code_commit_sha=git["commit_sha"],
        code_branch=git["branch"],
        git_dirty=git["dirty"],
        manifest_hash_sha256=manifest_hash,
        status="registered",
    )
    db.session.add(run)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return run


def complete_experiment_run(
    run_code: str,
    *,
    metrics: dict[str, Any],
) -> ExperimentRun:
    """Finaliza una ejecución registrada sin alterar su manifiesto inicial."""

    _assert_no_sensitive_keys(metrics, "metrics")
    run = get_experiment_run(run_code)
    if run.status != "registered":
        raise ExperimentRunError("La ejecución ya fue cerrada.")
    run.metrics_json = metrics
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return run


def fail_experiment_run(run_code: str, *, reason: str) -> ExperimentRun:
    """Registra un fallo sin incluir trazas que puedan contener secretos."""

    run = get_experiment_run(run_code)
    if run.status != "registered":
        raise ExperimentRunError("La ejecución ya fue cerrada.")
    normalized = _require_text(reason, "reason", max_length=2000)
    run.failure_reason = normalized
    run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return run


def get_experiment_run(run_code: str) -> ExperimentRun:
    run = db.session.execute(
        select(ExperimentRun).where(
            ExperimentRun.run_code == str(run_code).strip()
        )
    ).scalar_one_or_none()
    if run is None:
        raise ExperimentRunError("No existe la ejecución solicitada.")
    return run


def experiment_manifest(run: ExperimentRun) -> dict[str, Any]:
    """Vista exportable del manifiesto y resultado, sin secretos."""

    return {
        "run_code": run.run_code,
        "protocol_version": run.protocol_version,
        "dataset_version": run.dataset_version,
        "dataset_release_hash_sha256": run.dataset_release_hash_sha256,
        "model_name": run.model_name,
        "model_version": run.model_version,
        "run_type": run.run_type,
        "seed": run.seed,
        "hyperparameters": run.hyperparameters_json,
        "conditions": run.conditions_json,
        "environment": run.environment_json,
        "requirements_sha256": run.requirements_sha256,
        "package_snapshot_sha256": run.package_snapshot_sha256,
        "code_commit_sha": run.code_commit_sha,
        "code_branch": run.code_branch,
        "git_dirty": run.git_dirty,
        "manifest_hash_sha256": run.manifest_hash_sha256,
        "status": run.status,
        "metrics": run.metrics_json,
        "failure_reason": run.failure_reason,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
