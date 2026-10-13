"""Preparación de datos para investigación, ML y Transformers.

FASE 3 — Servicios
------------------
Este módulo construye registros reproducibles a partir de sesiones finalizadas.
No entrena modelos de IA. Tampoco expone las 60 respuestas O*NET como
predictores del dataset principal, evitando fuga de información (data leakage).
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    AssessmentSession,
    DataQualityReview,
    InterestResponse,
    ONetResponse,
    OpenResponse,
    SessionActivity,
    SessionSubject,
)


class DatasetServiceError(ValueError):
    """Error de dominio durante la preparación de un dataset."""


ML_TARGET_COLUMNS: tuple[str, ...] = (
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
)

# Variables cuya información puede revelar directamente la decisión profesional
# y que, por diseño metodológico, no forman parte del modelo principal.
SUBJECT_CODES: tuple[str, ...] = (
    "matematicas",
    "lengua_castellana",
    "ingles",
    "biologia",
    "quimica",
    "fisica",
    "sociales",
    "tecnologia_informatica",
    "artistica",
    "educacion_fisica",
    "emprendimiento",
    "otra",
)

ACTIVITY_CODES: tuple[str, ...] = (
    "deportes",
    "musica",
    "danza",
    "dibujo_diseno",
    "programacion_tecnologia",
    "videojuegos",
    "creacion_contenido",
    "lectura",
    "escritura",
    "voluntariado",
    "emprendimiento_ventas",
    "comunitaria",
    "reparacion_construccion",
    "ninguna",
    "otra",
)

EXCLUDED_PREDICTORS: frozenset[str] = frozenset(
    {
        "career_in_mind_text",
        "gender_self_reported",
        "institution_code",
    }
)


def _require_session_ready(session: AssessmentSession) -> None:
    """Comprueba que una sesión sea utilizable para construir datasets."""

    if session is None:
        raise DatasetServiceError("La sesión es obligatoria.")
    if session.status != "completed":
        raise DatasetServiceError(
            "Solo las sesiones finalizadas pueden convertirse en dataset."
        )
    if session.riasec_result is None:
        raise DatasetServiceError(
            "La sesión no posee un resultado RIASEC materializado."
        )


def _riasec_targets(session: AssessmentSession) -> dict[str, Any]:
    """Serializa las variables objetivo Y de una sesión."""

    result = session.riasec_result
    assert result is not None
    return {
        "score_r": result.score_r,
        "score_i": result.score_i,
        "score_a": result.score_a,
        "score_s": result.score_s,
        "score_e": result.score_e,
        "score_c": result.score_c,
        "profile_1": result.profile_1,
        "profile_2": result.profile_2,
        "profile_3": result.profile_3,
        "holland_code": result.holland_code,
        "tie_top1": result.tie_top1,
    }


def _interest_features(session: AssessmentSession) -> dict[str, int | None]:
    """Convierte G01-G12 normalizado a columnas para ML."""

    result = {f"g{index:02d}": None for index in range(1, 13)}
    for response in session.interest_responses:
        code = response.item.code.lower()
        if code in result:
            result[code] = response.response_value
    return result


def _subject_features(session: AssessmentSession) -> dict[str, Any]:
    """One-hot de materias seleccionadas más texto opcional de 'otra'."""

    features: dict[str, Any] = {
        f"mat_{code}": 0 for code in SUBJECT_CODES
    }
    features["mat_otra_texto"] = None
    for link in session.subject_links:
        key = f"mat_{link.subject.code}"
        features[key] = 1
        if link.subject.allows_other_text:
            features["mat_otra_texto"] = link.other_text
    return features


def _activity_features(session: AssessmentSession) -> dict[str, Any]:
    """One-hot de actividades actuales más texto opcional de 'otra'."""

    features: dict[str, Any] = {
        f"act_{code}": 0 for code in ACTIVITY_CODES
    }
    features["act_otra_texto"] = None
    for link in session.activity_links:
        key = f"act_{link.activity.code}"
        features[key] = 1
        if link.activity.allows_other_text:
            features["act_otra_texto"] = link.other_text
    return features


def _open_text_features(session: AssessmentSession) -> dict[str, str | None]:
    """Extrae T01-T03 y construye `texto_combinado` sin modificar originales."""

    values: dict[str, str | None] = {
        "t01_actividad_libre": None,
        "t02_experiencia_significativa": None,
        "t03_futuro": None,
    }
    mapping = {
        "T01": "t01_actividad_libre",
        "T02": "t02_experiencia_significativa",
        "T03": "t03_futuro",
    }

    for response in session.open_responses:
        field = mapping.get(response.prompt_code)
        if field:
            values[field] = response.response_text

    parts = [
        values["t01_actividad_libre"],
        values["t02_experiencia_significativa"],
        values["t03_futuro"],
    ]
    values["texto_combinado"] = " [SEP] ".join(
        part for part in parts if part
    ) or None
    return values


def build_ml_record(session: AssessmentSession) -> dict[str, Any]:
    """Construye una fila X/Y para ML sin respuestas O*NET como predictores.

    El registro contiene variables estructuradas, textos originales y los seis
    puntajes/etiquetas como Y. Deliberadamente NO incluye `IP01...IP60`,
    `response_raw` ni `response_score`.
    """

    _require_session_ready(session)

    record: dict[str, Any] = {
        "participant_code": session.participant.participant_code,
        "session_id": str(session.id),
        "age": session.age,
        "grade": session.grade,
        "municipality": session.municipality,
        "zone": session.zone,
        "collection_phase": session.collection_phase,
        "has_career_in_mind": session.has_career_in_mind,
    }
    record.update(_interest_features(session))
    record.update(_subject_features(session))
    record.update(_activity_features(session))
    record.update(_open_text_features(session))
    record.update(_riasec_targets(session))

    forbidden = {
        key
        for key in record
        if key.lower().startswith("ip")
        or key in {"response_raw", "response_score", *EXCLUDED_PREDICTORS}
    }
    if forbidden:
        raise DatasetServiceError(
            "Se detectaron variables prohibidas en el dataset ML: "
            f"{', '.join(sorted(forbidden))}."
        )

    return record


def build_transformer_record(session: AssessmentSession) -> dict[str, Any]:
    """Construye una fila compacta para experimentos NLP/Transformers."""

    _require_session_ready(session)
    texts = _open_text_features(session)
    return {
        "participant_code": session.participant.participant_code,
        "session_id": str(session.id),
        "collection_phase": session.collection_phase,
        **texts,
        **_riasec_targets(session),
    }


def build_master_audit_record(session: AssessmentSession) -> dict[str, Any]:
    """Construye un registro maestro auditable incluyendo las 60 respuestas.

    Esta función es deliberadamente diferente de `build_ml_record`: el maestro
    sí conserva IP01-IP60 para reproducibilidad y auditoría, pero esas columnas
    no deben reutilizarse como X en el modelo principal.
    """

    _require_session_ready(session)

    record: dict[str, Any] = {
        "participant_code": session.participant.participant_code,
        "session_id": str(session.id),
        "age": session.age,
        "grade": session.grade,
        "institution_code": session.institution_code,
        "municipality": session.municipality,
        "zone": session.zone,
        "gender_self_reported": session.gender_self_reported,
        "has_career_in_mind": session.has_career_in_mind,
        "career_in_mind_text": session.career_in_mind_text,
        "instrument_version": session.instrument_version.code,
    }

    ordered_responses = sorted(
        session.onet_responses,
        key=lambda response: response.item.item_index,
    )
    for response in ordered_responses:
        record[response.item.item_code] = response.response_raw

    record.update(_interest_features(session))
    record.update(_subject_features(session))
    record.update(_activity_features(session))
    record.update(_open_text_features(session))
    record.update(_riasec_targets(session))
    return record


def review_session_quality(
    session: AssessmentSession,
    *,
    quality_status: str,
    included_ml: bool = False,
    exclusion_reason: str | None = None,
    dataset_version: str | None = None,
) -> DataQualityReview:
    """Crea o actualiza la decisión de calidad de una sesión.

    Una sesión solo puede marcarse para ML cuando está finalizada y su estado
    de calidad es `valid`. Los estados `pending` y `excluded` fuerzan
    `included_ml=False` para impedir inclusiones accidentales.
    """

    if session is None:
        raise DatasetServiceError("La sesión es obligatoria.")

    normalized_status = str(quality_status).strip().lower()
    if normalized_status not in {"pending", "valid", "excluded"}:
        raise DatasetServiceError(
            "quality_status debe ser pending, valid o excluded."
        )

    if included_ml and normalized_status != "valid":
        raise DatasetServiceError(
            "Solo una sesión con quality_status='valid' puede incluirse en ML."
        )
    if included_ml and session.status != "completed":
        raise DatasetServiceError(
            "Solo una sesión finalizada puede incluirse en ML."
        )
    if normalized_status == "excluded" and not exclusion_reason:
        raise DatasetServiceError(
            "Una sesión excluida debe indicar exclusion_reason."
        )
    if included_ml and not dataset_version:
        raise DatasetServiceError(
            "Una sesión incluida en ML debe indicar dataset_version."
        )

    review = session.quality_review
    if review is None:
        review = DataQualityReview(session_id=session.id)
        db.session.add(review)

    review.quality_status = normalized_status
    review.exclusion_reason = (
        str(exclusion_reason).strip() if exclusion_reason else None
    )
    review.included_ml = bool(included_ml) if normalized_status == "valid" else False
    review.dataset_version = (
        str(dataset_version).strip() if dataset_version else None
    )
    review.reviewed_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return review


def get_eligible_sessions(*, included_ml_only: bool = True) -> list[AssessmentSession]:
    """Consulta sesiones finalizadas elegibles para investigación.

    Cuando `included_ml_only=True`, exige la decisión explícita del control de
    calidad (`included_ml = true`). Así un registro nunca entra al entrenamiento
    por accidente solo por estar finalizado.
    """

    statement = (
        select(AssessmentSession)
        .options(
            selectinload(AssessmentSession.participant),
            selectinload(AssessmentSession.instrument_version),
            selectinload(AssessmentSession.onet_responses).selectinload(
                ONetResponse.item
            ),
            selectinload(AssessmentSession.interest_responses).selectinload(
                InterestResponse.item
            ),
            selectinload(AssessmentSession.subject_links).selectinload(
                SessionSubject.subject
            ),
            selectinload(AssessmentSession.activity_links).selectinload(
                SessionActivity.activity
            ),
            selectinload(AssessmentSession.open_responses),
            selectinload(AssessmentSession.riasec_result),
            selectinload(AssessmentSession.quality_review),
        )
        .where(AssessmentSession.status == "completed")
        .order_by(AssessmentSession.started_at.asc())
    )

    if included_ml_only:
        statement = statement.join(
            DataQualityReview,
            DataQualityReview.session_id == AssessmentSession.id,
        ).where(
            DataQualityReview.quality_status == "valid",
            DataQualityReview.included_ml.is_(True),
        )

    return list(db.session.execute(statement).scalars().unique().all())


def build_dataset(
    sessions: Iterable[AssessmentSession],
    *,
    kind: str = "ml",
) -> list[dict[str, Any]]:
    """Convierte sesiones únicas en registros ML, Transformer o maestro."""

    builders = {
        "ml": build_ml_record,
        "transformer": build_transformer_record,
        "master": build_master_audit_record,
    }
    builder = builders.get(kind)
    if builder is None:
        raise DatasetServiceError(
            "kind debe ser 'ml', 'transformer' o 'master'."
        )

    records: list[dict[str, Any]] = []
    seen_sessions: set[uuid.UUID] = set()
    for session in sessions:
        if session.id in seen_sessions:
            continue
        seen_sessions.add(session.id)
        records.append(builder(session))
    return records


def export_records_to_csv(records: Iterable[dict[str, Any]]) -> str:
    """Serializa registros a CSV UTF-8 usando solo la biblioteca estándar.

    La función devuelve texto; decidir si se envía como descarga HTTP o se
    escribe en disco corresponderá a fases posteriores.
    """

    rows = list(records)
    if not rows:
        return ""

    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen_fields:
                fieldnames.append(key)
                seen_fields.add(key)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()

# ---------------------------------------------------------------------------
# FASE 14 — Módulo privado de investigadores
# ---------------------------------------------------------------------------

RESEARCH_DATASET_KINDS: tuple[str, ...] = (
    "results",
    "ml",
    "transformer",
    "master",
    "quality",
)


def _parse_optional_date(value: Any, field_name: str) -> date | None:
    """Convierte YYYY-MM-DD a ``date`` para filtros del panel."""

    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise DatasetServiceError(
            f"{field_name} debe usar el formato YYYY-MM-DD."
        ) from exc


def normalize_research_filters(values: Mapping[str, Any]) -> dict[str, Any]:
    """Normaliza y valida filtros permitidos para investigación.

    La función acepta ``request.args`` o un diccionario normal. No construye
    SQL a partir de texto libre y únicamente devuelve valores validados.
    """

    grade_raw = str(values.get("grade", "")).strip()
    grade: int | None = None
    if grade_raw:
        try:
            grade = int(grade_raw)
        except ValueError as exc:
            raise DatasetServiceError("grade debe ser 10 u 11.") from exc
        if grade not in {10, 11}:
            raise DatasetServiceError("grade debe ser 10 u 11.")

    zone = str(values.get("zone", "")).strip().lower() or None
    if zone not in {None, "urbana", "rural"}:
        raise DatasetServiceError("zone debe ser urbana o rural.")

    status = str(values.get("status", "")).strip().lower() or None
    if status not in {None, "created", "in_progress", "completed", "abandoned"}:
        raise DatasetServiceError("Estado de evaluación no válido.")

    quality_status = (
        str(values.get("quality_status", "")).strip().lower() or None
    )
    if quality_status not in {None, "pending", "valid", "excluded"}:
        raise DatasetServiceError("Estado de calidad no válido.")

    return {
        "grade": grade,
        "institution_code": (
            str(values.get("institution_code", "")).strip() or None
        ),
        "municipality": str(values.get("municipality", "")).strip() or None,
        "zone": zone,
        "status": status,
        "quality_status": quality_status,
        "started_from": _parse_optional_date(
            values.get("started_from"),
            "started_from",
        ),
        "started_to": _parse_optional_date(
            values.get("started_to"),
            "started_to",
        ),
    }


def _research_session_statement(
    filters: Mapping[str, Any] | None = None,
    *,
    completed_only: bool = False,
    included_ml_only: bool = False,
):
    """Construye una consulta SQLAlchemy segura para el panel investigador."""

    filters = dict(filters or {})
    statement = select(AssessmentSession).options(
        selectinload(AssessmentSession.participant),
        selectinload(AssessmentSession.instrument_version),
        selectinload(AssessmentSession.onet_responses).selectinload(
            ONetResponse.item
        ),
        selectinload(AssessmentSession.interest_responses).selectinload(
            InterestResponse.item
        ),
        selectinload(AssessmentSession.subject_links).selectinload(
            SessionSubject.subject
        ),
        selectinload(AssessmentSession.activity_links).selectinload(
            SessionActivity.activity
        ),
        selectinload(AssessmentSession.open_responses),
        selectinload(AssessmentSession.riasec_result),
        selectinload(AssessmentSession.quality_review),
    )

    needs_quality_join = bool(filters.get("quality_status")) or included_ml_only
    if needs_quality_join:
        statement = statement.outerjoin(
            DataQualityReview,
            DataQualityReview.session_id == AssessmentSession.id,
        )

    if completed_only:
        statement = statement.where(AssessmentSession.status == "completed")
    elif filters.get("status"):
        statement = statement.where(
            AssessmentSession.status == filters["status"]
        )

    if filters.get("grade"):
        statement = statement.where(AssessmentSession.grade == filters["grade"])
    if filters.get("institution_code"):
        statement = statement.where(
            AssessmentSession.institution_code == filters["institution_code"]
        )
    if filters.get("municipality"):
        statement = statement.where(
            AssessmentSession.municipality == filters["municipality"]
        )
    if filters.get("zone"):
        statement = statement.where(AssessmentSession.zone == filters["zone"])

    started_from = filters.get("started_from")
    if started_from:
        start_dt = datetime.combine(started_from, time.min, tzinfo=timezone.utc)
        statement = statement.where(AssessmentSession.started_at >= start_dt)

    started_to = filters.get("started_to")
    if started_to:
        end_dt = datetime.combine(
            started_to + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        statement = statement.where(AssessmentSession.started_at < end_dt)

    quality_status = filters.get("quality_status")
    if quality_status == "pending":
        statement = statement.where(
            or_(
                DataQualityReview.id.is_(None),
                DataQualityReview.quality_status == "pending",
            )
        )
    elif quality_status:
        statement = statement.where(
            DataQualityReview.quality_status == quality_status
        )

    if included_ml_only:
        statement = statement.where(
            DataQualityReview.quality_status == "valid",
            DataQualityReview.included_ml.is_(True),
        )

    return statement.order_by(AssessmentSession.started_at.desc())


def get_research_sessions(
    filters: Mapping[str, Any] | None = None,
    *,
    completed_only: bool = False,
    included_ml_only: bool = False,
    limit: int | None = None,
) -> list[AssessmentSession]:
    """Recupera sesiones para dashboard o exportación con relaciones cargadas."""

    statement = _research_session_statement(
        filters,
        completed_only=completed_only,
        included_ml_only=included_ml_only,
    )
    if limit is not None:
        if limit < 1:
            raise DatasetServiceError("limit debe ser mayor que cero.")
        statement = statement.limit(limit)

    return list(db.session.execute(statement).scalars().unique().all())


def get_research_summary(
    filters: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    """Resume el estado de recolección y control de calidad."""

    sessions = get_research_sessions(filters)
    quality_statuses = [
        (
            session.quality_review.quality_status
            if session.quality_review is not None
            else "pending"
        )
        for session in sessions
    ]

    return {
        "participants": len({session.participant_id for session in sessions}),
        "sessions": len(sessions),
        "completed": sum(session.status == "completed" for session in sessions),
        "in_progress": sum(
            session.status == "in_progress" for session in sessions
        ),
        "abandoned": sum(session.status == "abandoned" for session in sessions),
        "quality_pending": quality_statuses.count("pending"),
        "quality_valid": quality_statuses.count("valid"),
        "quality_excluded": quality_statuses.count("excluded"),
        "included_ml": sum(
            bool(session.quality_review and session.quality_review.included_ml)
            for session in sessions
        ),
    }


def get_research_filter_options() -> dict[str, list[str]]:
    """Devuelve valores disponibles para filtros sin exponer respuestas."""

    institutions = db.session.execute(
        select(AssessmentSession.institution_code)
        .distinct()
        .order_by(AssessmentSession.institution_code.asc())
    ).scalars().all()
    municipalities = db.session.execute(
        select(AssessmentSession.municipality)
        .distinct()
        .order_by(AssessmentSession.municipality.asc())
    ).scalars().all()
    return {
        "institutions": [value for value in institutions if value],
        "municipalities": [value for value in municipalities if value],
    }


def build_results_record(session: AssessmentSession) -> dict[str, Any]:
    """Fila anonimizada para análisis estadístico de resultados RIASEC."""

    _require_session_ready(session)
    result = session.riasec_result
    assert result is not None
    return {
        "participant_code": session.participant.participant_code,
        "session_id": str(session.id),
        "age": session.age,
        "grade": session.grade,
        "institution_code": session.institution_code,
        "municipality": session.municipality,
        "zone": session.zone,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": (
            session.completed_at.isoformat() if session.completed_at else None
        ),
        "duration_seconds": session.duration_seconds,
        **_riasec_targets(session),
        "top1_candidates": "|".join(result.top1_candidates or []),
        "scoring_version": result.scoring_version,
    }


def build_quality_record(session: AssessmentSession) -> dict[str, Any]:
    """Fila de trazabilidad/calidad para una sesión, incluso incompleta."""

    review = session.quality_review
    response_times = [
        response.response_time_ms
        for response in session.onet_responses
        if response.response_time_ms is not None
    ]
    answered_onet = len(session.onet_responses)
    return {
        "participant_code": session.participant.participant_code,
        "session_id": str(session.id),
        "status": session.status,
        "current_stage": session.current_stage,
        "current_item_index": session.current_item_index,
        "grade": session.grade,
        "institution_code": session.institution_code,
        "municipality": session.municipality,
        "zone": session.zone,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": (
            session.completed_at.isoformat() if session.completed_at else None
        ),
        "duration_seconds": session.duration_seconds,
        "onet_answered": answered_onet,
        "onet_missing": max(60 - answered_onet, 0),
        "onet_completion_percentage": round(answered_onet / 60 * 100, 2),
        "interest_answered": len(session.interest_responses),
        "subjects_selected": len(session.subject_links),
        "activities_selected": len(session.activity_links),
        "open_responses": len(session.open_responses),
        "tts_items_used": sum(
            bool(response.tts_used) for response in session.onet_responses
        ),
        "changed_count_total": sum(
            response.changed_count for response in session.onet_responses
        ),
        "mean_response_time_ms": (
            round(sum(response_times) / len(response_times), 2)
            if response_times
            else None
        ),
        "quality_status": review.quality_status if review else "pending",
        "included_ml": bool(review and review.included_ml),
        "exclusion_reason": review.exclusion_reason if review else None,
        "dataset_version": review.dataset_version if review else None,
        "reviewed_at": (
            review.reviewed_at.isoformat()
            if review and review.reviewed_at
            else None
        ),
    }


def build_research_dataset(
    kind: str,
    filters: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Construye uno de los datasets autorizados desde el panel privado."""

    normalized_kind = str(kind).strip().lower()
    if normalized_kind not in RESEARCH_DATASET_KINDS:
        raise DatasetServiceError("Tipo de dataset no válido.")

    if normalized_kind in {"ml", "transformer"}:
        sessions = get_research_sessions(
            filters,
            completed_only=True,
            included_ml_only=True,
        )
        return build_dataset(sessions, kind=normalized_kind)

    if normalized_kind == "results":
        sessions = get_research_sessions(filters, completed_only=True)
        return [build_results_record(session) for session in sessions]

    if normalized_kind == "master":
        sessions = get_research_sessions(filters, completed_only=True)
        return build_dataset(sessions, kind="master")

    sessions = get_research_sessions(filters)
    return [build_quality_record(session) for session in sessions]


def export_records_to_xlsx(
    records: Iterable[dict[str, Any]],
    *,
    sheet_title: str = "dataset",
) -> bytes:
    """Serializa registros a XLSX con encabezados, autofiltro y ancho legible."""

    try:
        from openpyxl import Workbook
        from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise DatasetServiceError(
            "La exportación Excel requiere openpyxl instalado."
        ) from exc

    rows = list(records)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = (sheet_title or "dataset")[:31]

    if not rows:
        worksheet.append(["sin_registros"])
        worksheet.append(["No hay registros para los filtros seleccionados."])
    else:
        fieldnames: list[str] = []
        seen_fields: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen_fields:
                    fieldnames.append(key)
                    seen_fields.add(key)

        worksheet.append(fieldnames)

        def excel_safe(value: Any) -> Any:
            if isinstance(value, str):
                return ILLEGAL_CHARACTERS_RE.sub("", value)
            if isinstance(value, (list, tuple, set)):
                return "|".join(str(item) for item in value)
            if isinstance(value, dict):
                return str(value)
            return value

        for row in rows:
            worksheet.append(
                [excel_safe(row.get(field)) for field in fieldnames]
            )

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for index, field in enumerate(fieldnames, start=1):
            sample_lengths = [len(str(field))]
            for row in rows[:100]:
                value = row.get(field)
                if value is not None:
                    sample_lengths.append(len(str(value)))
            width = min(max(sample_lengths) + 2, 45)
            worksheet.column_dimensions[get_column_letter(index)].width = width

    binary = io.BytesIO()
    workbook.save(binary)
    return binary.getvalue()

