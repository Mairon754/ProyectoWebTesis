"""Congelación reproducible del dataset científico primario.

FASE 5 — Dataset científico definitivo
--------------------------------------
Este servicio crea releases inmutables a partir de sesiones explícitamente
validadas para ML. No realiza entrenamiento ni balanceo sintético.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy import select

from app.extensions import db
from app.models import DatasetRelease, DatasetReleaseMember
from app.services.dataset_service import (
    PRIMARY_EXPERIMENT_CONTRACT_VERSION,
    PRIMARY_EXPERIMENT_DERIVED_TARGETS,
    PRIMARY_EXPERIMENT_METADATA,
    PRIMARY_EXPERIMENT_PREDICTORS,
    build_primary_experiment_record,
    get_eligible_sessions,
)
from app.services.riasec_protocol import (
    INSTRUMENT_VERIFICATION_VERIFIED,
    PRIMARY_TARGET_COLUMNS,
    TARGET_PROTOCOL_VERSION,
)


SPLIT_PROTOCOL_VERSION = "PARTICIPANT_HASH_ORDER_V1"


class DatasetReleaseError(ValueError):
    """Error de contrato o congelación del dataset."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_ratio(value: Any, name: str) -> Decimal:
    try:
        ratio = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DatasetReleaseError(f"{name} debe ser numérico.") from exc
    if ratio <= 0 or ratio >= 1:
        raise DatasetReleaseError(f"{name} debe estar entre 0 y 1.")
    return ratio


def validate_split_ratios(
    train_ratio: Any,
    validation_ratio: Any,
    test_ratio: Any,
) -> tuple[Decimal, Decimal, Decimal]:
    """Valida proporciones explícitas sin imponer una partición no aprobada."""

    train = _normalize_ratio(train_ratio, "train_ratio")
    validation = _normalize_ratio(validation_ratio, "validation_ratio")
    test = _normalize_ratio(test_ratio, "test_ratio")
    if train + validation + test != Decimal("1"):
        raise DatasetReleaseError(
            "train_ratio + validation_ratio + test_ratio debe ser exactamente 1."
        )
    return train, validation, test


def _split_counts(
    total: int,
    train: Decimal,
    validation: Decimal,
) -> tuple[int, int, int]:
    train_count = math.floor(total * float(train))
    validation_count = math.floor(total * float(validation))
    test_count = total - train_count - validation_count
    if min(train_count, validation_count, test_count) < 1:
        raise DatasetReleaseError(
            "La cantidad de registros no permite obtener train, validation y "
            "test no vacíos con las proporciones indicadas."
        )
    return train_count, validation_count, test_count


def _deterministic_order_key(version: str, participant_code: str) -> str:
    return _sha256(
        f"{SPLIT_PROTOCOL_VERSION}|{version}|{participant_code}"
    )


def assign_participant_splits(
    participant_codes: Iterable[str],
    *,
    version: str,
    train_ratio: Any,
    validation_ratio: Any,
    test_ratio: Any,
) -> dict[str, str]:
    """Asigna splits deterministas a nivel de participante.

    La asignación se calcula una sola vez para un release congelado. Nunca se
    dividen respuestas de un mismo participante entre conjuntos.
    """

    train, validation, test = validate_split_ratios(
        train_ratio, validation_ratio, test_ratio
    )
    codes = [str(code).strip().upper() for code in participant_codes]
    if not codes or any(not code for code in codes):
        raise DatasetReleaseError("La lista de participantes no puede estar vacía.")
    if len(set(codes)) != len(codes):
        raise DatasetReleaseError(
            "Un participante aparece más de una vez; no se puede congelar el "
            "release sin resolver la duplicidad de sesiones."
        )

    train_count, validation_count, _ = _split_counts(
        len(codes), train, validation
    )
    ordered = sorted(
        codes,
        key=lambda code: (_deterministic_order_key(version, code), code),
    )

    assignments: dict[str, str] = {}
    for index, code in enumerate(ordered):
        if index < train_count:
            split = "train"
        elif index < train_count + validation_count:
            split = "validation"
        else:
            split = "test"
        assignments[code] = split
    return assignments


def dataset_contract() -> dict[str, Any]:
    """Contrato explícito X/Y que deben compartir todas las arquitecturas."""

    return {
        "contract_version": PRIMARY_EXPERIMENT_CONTRACT_VERSION,
        "metadata_columns": list(PRIMARY_EXPERIMENT_METADATA),
        "predictor_columns": list(PRIMARY_EXPERIMENT_PREDICTORS),
        "primary_target_columns": list(PRIMARY_TARGET_COLUMNS),
        "derived_target_columns": list(PRIMARY_EXPERIMENT_DERIVED_TARGETS),
        "target_protocol_version": TARGET_PROTOCOL_VERSION,
        "forbidden_predictor_prefixes": ["IP"],
        "forbidden_predictors": [
            "score_r",
            "score_i",
            "score_a",
            "score_s",
            "score_e",
            "score_c",
            "profile_1",
            "profile_2",
            "profile_3",
            "holland_code",
            "tie_top1",
            "participant_code",
            "collection_phase",
        ],
    }


def dataset_dictionary() -> dict[str, Any]:
    """Diccionario de datos del contrato experimental primario."""

    return {
        "contract_version": PRIMARY_EXPERIMENT_CONTRACT_VERSION,
        "columns": {
            "participant_code": {
                "role": "metadata",
                "description": (
                    "Código seudónimo aleatorio para trazabilidad; no usar como X."
                ),
            },
            "collection_phase": {
                "role": "metadata",
                "description": "Fase de recolección pilot/final; no usar como X.",
            },
            "texto_combinado": {
                "role": "predictor",
                "description": (
                    "Texto T01-T03 concatenado con separador [SEP]. "
                    "Es la X común del experimento principal."
                ),
            },
            **{
                column: {
                    "role": "primary_target",
                    "description": (
                        "Puntaje RIASEC dimensional de referencia en escala 0-40."
                    ),
                }
                for column in PRIMARY_TARGET_COLUMNS
            },
            "profile_1": {
                "role": "derived_target",
                "description": "Primera dimensión solo cuando existe máximo único.",
            },
            "profile_2": {
                "role": "derived_target",
                "description": "Segunda posición ordenada cuando es inequívoca.",
            },
            "profile_3": {
                "role": "derived_target",
                "description": "Tercera posición ordenada cuando es inequívoca.",
            },
            "holland_code": {
                "role": "derived_target",
                "description": (
                    "Código Holland de tres letras solo si las tres posiciones "
                    "superiores son únicas."
                ),
            },
            "tie_top1": {
                "role": "derived_target",
                "description": "Indica empate exacto en la puntuación máxima.",
            },
            "split": {
                "role": "partition",
                "description": "Partición congelada: train, validation o test.",
            },
        },
        "predictor_columns": list(PRIMARY_EXPERIMENT_PREDICTORS),
        "primary_target_columns": list(PRIMARY_TARGET_COLUMNS),
        "derived_target_columns": list(PRIMARY_EXPERIMENT_DERIVED_TARGETS),
    }


def _eligible_for_release(collection_phase: str):
    sessions = get_eligible_sessions(included_ml_only=True)
    selected = [
        session
        for session in sessions
        if session.collection_phase == collection_phase
    ]
    if not selected:
        raise DatasetReleaseError(
            f"No hay sesiones elegibles para collection_phase={collection_phase!r}."
        )

    participant_codes = [
        session.participant.participant_code for session in selected
    ]
    if len(set(participant_codes)) != len(participant_codes):
        raise DatasetReleaseError(
            "Hay más de una sesión elegible para al menos un participante. "
            "Debe resolverse cuál sesión integra el dataset antes de congelarlo."
        )

    if collection_phase == "final":
        for session in selected:
            if session.grade != 11:
                raise DatasetReleaseError(
                    "El release final contiene una sesión fuera de grado 11."
                )
            if session.instrument_version.verification_status != (
                INSTRUMENT_VERIFICATION_VERIFIED
            ):
                raise DatasetReleaseError(
                    "El release final está bloqueado: el instrumento todavía "
                    "no posee validación profesional/local documentada."
                )
    return selected


def freeze_dataset_release(
    *,
    version: str,
    collection_phase: str,
    train_ratio: Any,
    validation_ratio: Any,
    test_ratio: Any,
) -> DatasetRelease:
    """Congela un release con registros, splits, esquema y hashes persistidos."""

    normalized_version = str(version).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", normalized_version):
        raise DatasetReleaseError(
            "version solo admite letras, números, punto, guion y guion bajo "
            "(máximo 40 caracteres)."
        )
    if collection_phase not in {"pilot", "final"}:
        raise DatasetReleaseError("collection_phase debe ser pilot o final.")
    if db.session.execute(
        select(DatasetRelease.id).where(DatasetRelease.version == normalized_version)
    ).scalar_one_or_none() is not None:
        raise DatasetReleaseError("Ya existe un release con esa versión.")

    train, validation, test = validate_split_ratios(
        train_ratio, validation_ratio, test_ratio
    )
    sessions = _eligible_for_release(collection_phase)
    records: list[dict[str, Any]] = []
    by_code: dict[str, Any] = {}
    for session in sessions:
        record = build_primary_experiment_record(session)
        code = record["participant_code"]
        records.append(record)
        by_code[code] = session

    assignments = assign_participant_splits(
        [record["participant_code"] for record in records],
        version=normalized_version,
        train_ratio=train,
        validation_ratio=validation,
        test_ratio=test,
    )

    contract = dataset_contract()
    schema_hash = _sha256(contract)
    instrument_codes = {
        session.instrument_version.code for session in sessions
    }
    instrument_hashes = {
        session.instrument_version.local_content_hash_sha256
        for session in sessions
    }
    scoring_hashes = {
        session.instrument_version.scoring_spec_sha256 for session in sessions
    }
    if len(instrument_codes) != 1 or len(instrument_hashes) != 1 or len(scoring_hashes) != 1:
        raise DatasetReleaseError(
            "El release mezcla versiones o hashes científicos distintos."
        )
    instrument_code = next(iter(instrument_codes))
    instrument_hash = next(iter(instrument_hashes))
    scoring_hash = next(iter(scoring_hashes))
    if not instrument_hash or not scoring_hash:
        raise DatasetReleaseError("Faltan hashes científicos del instrumento/scoring.")

    frozen_rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda row: row["participant_code"]):
        row = dict(record)
        row["split"] = assignments[row["participant_code"]]
        frozen_rows.append(row)

    release_payload = {
        "version": normalized_version,
        "collection_phase": collection_phase,
        "contract": contract,
        "split_protocol_version": SPLIT_PROTOCOL_VERSION,
        "ratios": {
            "train": str(train),
            "validation": str(validation),
            "test": str(test),
        },
        "instrument_version_code": instrument_code,
        "instrument_content_hash_sha256": instrument_hash,
        "scoring_spec_sha256": scoring_hash,
        "records": frozen_rows,
    }
    release_hash = _sha256(release_payload)

    release = DatasetRelease(
        version=normalized_version,
        status="frozen",
        collection_phase=collection_phase,
        contract_version=PRIMARY_EXPERIMENT_CONTRACT_VERSION,
        target_protocol_version=TARGET_PROTOCOL_VERSION,
        split_protocol_version=SPLIT_PROTOCOL_VERSION,
        train_ratio=train,
        validation_ratio=validation,
        test_ratio=test,
        instrument_version_code=instrument_code,
        instrument_content_hash_sha256=instrument_hash,
        scoring_spec_sha256=scoring_hash,
        schema_hash_sha256=schema_hash,
        release_hash_sha256=release_hash,
        record_count=len(frozen_rows),
    )
    db.session.add(release)
    db.session.flush()

    for row in frozen_rows:
        record_hash = _sha256(row)
        db.session.add(
            DatasetReleaseMember(
                release_id=release.id,
                participant_code=row["participant_code"],
                split_name=row["split"],
                record_hash_sha256=record_hash,
                record_json=row,
            )
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return release


def release_manifest(release: DatasetRelease) -> dict[str, Any]:
    """Genera manifiesto verificable sin alterar el release."""

    split_counts = Counter(member.split_name for member in release.members)
    top1_counts = Counter(
        (member.record_json or {}).get("profile_1") or "TIE_OR_NONE"
        for member in release.members
    )
    return {
        "version": release.version,
        "status": release.status,
        "collection_phase": release.collection_phase,
        "contract_version": release.contract_version,
        "target_protocol_version": release.target_protocol_version,
        "split_protocol_version": release.split_protocol_version,
        "ratios": {
            "train": str(release.train_ratio),
            "validation": str(release.validation_ratio),
            "test": str(release.test_ratio),
        },
        "record_count": release.record_count,
        "split_counts": dict(sorted(split_counts.items())),
        "profile_1_distribution": dict(sorted(top1_counts.items())),
        "instrument_version_code": release.instrument_version_code,
        "instrument_content_hash_sha256": (
            release.instrument_content_hash_sha256
        ),
        "scoring_spec_sha256": release.scoring_spec_sha256,
        "schema_hash_sha256": release.schema_hash_sha256,
        "release_hash_sha256": release.release_hash_sha256,
        "created_at": release.created_at.isoformat() if release.created_at else None,
        "frozen_at": release.frozen_at.isoformat() if release.frozen_at else None,
        "balance_note": (
            "Distribución observada; no se aplicó sobremuestreo, submuestreo "
            "ni balanceo sintético al congelar el release."
        ),
    }


def get_dataset_release(version: str) -> DatasetRelease:
    release = db.session.execute(
        select(DatasetRelease).where(DatasetRelease.version == str(version).strip())
    ).scalar_one_or_none()
    if release is None:
        raise DatasetReleaseError("No existe el release solicitado.")
    return release


def export_release_records(
    release: DatasetRelease,
    *,
    split_name: str | None = None,
) -> list[dict[str, Any]]:
    """Devuelve snapshots congelados; opcionalmente filtra un split."""

    if split_name not in {None, "train", "validation", "test"}:
        raise DatasetReleaseError("split_name no válido.")
    members = release.members
    if split_name is not None:
        members = [member for member in members if member.split_name == split_name]
    return [dict(member.record_json) for member in members]
