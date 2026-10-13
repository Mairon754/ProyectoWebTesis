"""Lógica de negocio del flujo de evaluación.

FASE 3 — Servicios
------------------
Las futuras rutas Flask delegarán en este módulo la creación de sesiones,
consulta del instrumento, guardado de respuestas, progreso y finalización.
Aquí se validan reglas del dominio que no pertenecen a los modelos ni al HTML.
"""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Activity,
    AssessmentSession,
    ConsentRecord,
    InstrumentVersion,
    InterestItem,
    InterestResponse,
    ONetItem,
    ONetResponse,
    OpenResponse,
    Participant,
    SessionActivity,
    SessionSubject,
    Subject,
)
from app.services.riasec_service import (
    EXPECTED_TOTAL_ITEMS,
    RiasecScoringError,
    calculate_session_result,
)
from app.services.riasec_protocol import INSTRUMENT_VERIFICATION_VERIFIED

DEFAULT_INSTRUMENT_VERSION = "IP_ES_60_V1"
CURRENT_CONSENT_VERSION = "CONS_V2_LEGAL_2026"
MAX_SUBJECTS = 3
VALID_STAGES = {
    "demographics",
    "onet",
    "interests",
    "subjects",
    "activities",
    "open_questions",
    "results",
    "completed",
}
VALID_DEVICE_TYPES = {"mobile", "tablet", "desktop", "unknown"}
VALID_CAREER_INTENT = {"si", "no", "no_estoy_seguro"}
VALID_ZONES = {"urbana", "rural"}
INTEREST_CODES = {f"G{index:02d}" for index in range(1, 13)}
VALID_GENDERS = {
    "mujer",
    "hombre",
    "no_binario",
    "otro",
    "prefiero_no_responder",
}


class AssessmentServiceError(ValueError):
    """Error base de las reglas del flujo de evaluación."""


class AssessmentNotFoundError(AssessmentServiceError):
    """La sesión solicitada no existe."""


class AssessmentConflictError(AssessmentServiceError):
    """El estado actual impide realizar la operación solicitada."""


class AssessmentValidationError(AssessmentServiceError):
    """Los datos recibidos incumplen una regla del dominio."""


def utcnow() -> datetime:
    """Fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


def _as_uuid(value: uuid.UUID | str, field_name: str) -> uuid.UUID:
    """Convierte un identificador externo a UUID con error de dominio claro."""

    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssessmentValidationError(
            f"{field_name} no contiene un UUID válido."
        ) from exc


def _clean_text(value: Any, *, required: bool = False) -> str | None:
    """Normaliza cadenas externas sin convertir valores arbitrarios a texto."""

    if value is None:
        if required:
            raise AssessmentValidationError(
                "Existe un campo de texto obligatorio vacío."
            )
        return None
    if not isinstance(value, str):
        raise AssessmentValidationError("Se esperaba un valor de texto.")

    cleaned = value.strip()
    if required and not cleaned:
        raise AssessmentValidationError("Existe un campo de texto obligatorio vacío.")
    return cleaned or None


def _commit() -> None:
    """Confirma la transacción y deja la sesión utilizable si la BD falla."""

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _generate_participant_code() -> str:
    """Genera un código anónimo no secuencial y legible."""

    return f"RIA-{secrets.token_hex(4).upper()}"


def _get_or_create_participant(participant_code: str | None) -> Participant:
    """Recupera o crea un participante anonimizado."""

    if participant_code:
        cleaned = participant_code.strip().upper()
        participant = db.session.execute(
            select(Participant).where(Participant.participant_code == cleaned)
        ).scalar_one_or_none()
        if participant:
            if not participant.is_active:
                raise AssessmentConflictError(
                    "El participante indicado se encuentra inactivo."
                )
            return participant
    else:
        cleaned = _generate_participant_code()

    # Una colisión del token es extremadamente improbable. Aun así, se prueba
    # la unicidad antes de persistir para no depender del error SQL.
    while db.session.execute(
        select(Participant.id).where(Participant.participant_code == cleaned)
    ).scalar_one_or_none() is not None:
        cleaned = _generate_participant_code()

    participant = Participant(participant_code=cleaned)
    db.session.add(participant)
    db.session.flush()
    return participant


def _get_instrument_version(code: str) -> InstrumentVersion:
    """Obtiene una versión activa y utilizable del instrumento."""

    version = db.session.execute(
        select(InstrumentVersion).where(InstrumentVersion.code == code)
    ).scalar_one_or_none()

    if version is None:
        raise AssessmentValidationError(
            f"No existe la versión de instrumento '{code}'."
        )
    if not version.is_active or not version.instrument.is_active:
        raise AssessmentConflictError(
            "La versión del instrumento solicitada está inactiva."
        )
    if version.total_items != EXPECTED_TOTAL_ITEMS:
        raise AssessmentValidationError(
            "La versión configurada para el Short Form debe declarar 60 ítems."
        )
    return version


def _validate_demographics(
    data: Mapping[str, Any],
    *,
    collection_phase: str,
    authorized_institution_codes: set[str],
) -> dict[str, Any]:
    """Valida y normaliza la información demográfica de una sesión.

    En la recolección final se aplican los criterios aprobados para la muestra:
    grado 11, San Andrés de Tumaco e institución previamente autorizada.
    """

    try:
        age = int(data["age"])
        grade = int(data["grade"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AssessmentValidationError(
            "Edad y grado son obligatorios y deben ser numéricos."
        ) from exc

    if not 14 <= age <= 25:
        raise AssessmentValidationError("La edad debe estar entre 14 y 25 años.")
    if grade not in {10, 11}:
        raise AssessmentValidationError("El grado debe ser 10 u 11.")

    institution_code = _clean_text(data.get("institution_code"), required=True)
    municipality = _clean_text(data.get("municipality"), required=True)
    assert institution_code is not None
    assert municipality is not None
    institution_code = institution_code.upper()

    if collection_phase == "final":
        if grade != 11:
            raise AssessmentValidationError(
                "La recolección final está restringida a estudiantes de grado 11."
            )
        if municipality.strip().casefold() not in {
            "san andrés de tumaco".casefold(),
            "tumaco".casefold(),
        }:
            raise AssessmentValidationError(
                "La recolección final está restringida a San Andrés de Tumaco."
            )
        if institution_code not in authorized_institution_codes:
            raise AssessmentValidationError(
                "La institución no está autorizada para la recolección final."
            )

    zone = _clean_text(data.get("zone"), required=True)
    assert zone is not None
    zone = zone.lower()
    if zone not in VALID_ZONES:
        raise AssessmentValidationError("La zona debe ser 'urbana' o 'rural'.")

    career_intent = _clean_text(data.get("has_career_in_mind"), required=True)
    assert career_intent is not None
    career_intent = career_intent.lower()
    if career_intent not in VALID_CAREER_INTENT:
        raise AssessmentValidationError(
            "has_career_in_mind debe ser si, no o no_estoy_seguro."
        )

    gender = _clean_text(data.get("gender_self_reported"))
    if gender:
        gender = gender.lower()
        if gender not in VALID_GENDERS:
            raise AssessmentValidationError("El género reportado no es válido.")

    device_type = _clean_text(data.get("device_type")) or "unknown"
    device_type = device_type.lower()
    if device_type not in VALID_DEVICE_TYPES:
        raise AssessmentValidationError("El tipo de dispositivo no es válido.")

    return {
        "age": age,
        "grade": grade,
        "institution_code": institution_code,
        "municipality": municipality,
        "zone": zone,
        "gender_self_reported": gender,
        "has_career_in_mind": career_intent,
        "career_in_mind_text": _clean_text(data.get("career_in_mind_text")),
        "device_type": device_type,
    }


def create_assessment(
    *,
    demographics: Mapping[str, Any],
    consent_version: str,
    consent_accepted: bool,
    assent_accepted: bool | None = None,
    guardian_consent_required: bool = False,
    guardian_consent_reference: str | None = None,
    collection_method: str = "digital",
    participant_code: str | None = None,
    instrument_version_code: str = DEFAULT_INSTRUMENT_VERSION,
) -> AssessmentSession:
    """Crea participante, consentimiento y sesión en una sola transacción.

    La función no acepta datos personales directos. `participant_code` puede
    omitirse para que el sistema genere un identificador anónimo aleatorio.
    """

    if consent_accepted is not True:
        raise AssessmentValidationError(
            "No se puede crear la evaluación sin consentimiento aceptado."
        )

    consent_version = _clean_text(consent_version, required=True)
    assert consent_version is not None
    if consent_version != CURRENT_CONSENT_VERSION:
        raise AssessmentValidationError(
            "La versión de consentimiento no corresponde a la versión "
            "vigente de la plataforma."
        )

    if collection_method not in {"digital", "paper", "institutional"}:
        raise AssessmentValidationError("Método de consentimiento no válido.")

    collection_phase = str(
        current_app.config.get("COLLECTION_PHASE", "pilot")
    ).strip().lower()
    if collection_phase not in {"pilot", "final"}:
        raise AssessmentValidationError(
            "La fase de recolección configurada no es válida."
        )

    authorized_institution_codes = {
        str(code).strip().upper()
        for code in current_app.config.get("AUTHORIZED_INSTITUTION_CODES", ())
        if str(code).strip()
    }

    normalized_demographics = _validate_demographics(
        demographics,
        collection_phase=collection_phase,
        authorized_institution_codes=authorized_institution_codes,
    )

    is_minor = normalized_demographics["age"] < 18
    cleaned_guardian_reference = _clean_text(guardian_consent_reference)

    if is_minor:
        if guardian_consent_required is not True:
            raise AssessmentValidationError(
                "Los participantes menores de edad requieren consentimiento "
                "previo del acudiente."
            )
        if assent_accepted is not True:
            raise AssessmentValidationError(
                "Los participantes menores de edad requieren asentimiento propio."
            )
        if not cleaned_guardian_reference:
            raise AssessmentValidationError(
                "Falta la referencia verificable del consentimiento del acudiente."
            )
        if not re.fullmatch(
            r"[A-Za-z0-9_-]{6,100}",
            cleaned_guardian_reference,
        ):
            raise AssessmentValidationError(
                "La referencia del consentimiento del acudiente debe contener "
                "solo letras, números, guion o guion bajo."
            )
    else:
        if guardian_consent_required:
            raise AssessmentValidationError(
                "No debe marcarse consentimiento de acudiente para participantes "
                "de 18 años o más."
            )
        if cleaned_guardian_reference:
            raise AssessmentValidationError(
                "Un participante adulto no debe registrar referencia de acudiente."
            )
        if assent_accepted not in {None, True}:
            raise AssessmentValidationError(
                "El consentimiento del participante adulto no es válido."
            )

    try:
        participant = _get_or_create_participant(participant_code)
        instrument_version = _get_instrument_version(instrument_version_code)

        if (
            collection_phase == "final"
            and instrument_version.verification_status
            != INSTRUMENT_VERIFICATION_VERIFIED
        ):
            raise AssessmentConflictError(
                "La recolección final está bloqueada porque la versión RIASEC "
                "aún no cuenta con verificación científica documentada."
            )

        consent = ConsentRecord(
            participant_id=participant.id,
            consent_version=consent_version,
            consent_accepted=True,
            assent_accepted=assent_accepted,
            guardian_consent_required=guardian_consent_required,
            guardian_consent_reference=cleaned_guardian_reference,
            collection_method=collection_method,
        )
        db.session.add(consent)
        db.session.flush()

        assessment = AssessmentSession(
            participant_id=participant.id,
            consent_id=consent.id,
            instrument_version_id=instrument_version.id,
            status="in_progress",
            current_stage="onet",
            current_item_index=1,
            collection_phase=collection_phase,
            **normalized_demographics,
        )
        db.session.add(assessment)
        db.session.commit()
        return assessment
    except (AssessmentServiceError, IntegrityError):
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


def get_assessment(session_id: uuid.UUID | str) -> AssessmentSession:
    """Obtiene una sesión o produce un error de dominio 404-ready."""

    parsed = _as_uuid(session_id, "session_id")
    assessment = db.session.get(AssessmentSession, parsed)
    if assessment is None:
        raise AssessmentNotFoundError("La evaluación solicitada no existe.")
    return assessment


def get_questions(session_id: uuid.UUID | str) -> list[dict[str, Any]]:
    """Devuelve preguntas oficiales en orden sin revelar el área RIASEC.

    El área no se entrega al frontend para no inducir la respuesta del
    estudiante. Permanece disponible exclusivamente en el backend.
    """

    assessment = get_assessment(session_id)
    items = db.session.execute(
        select(ONetItem)
        .where(
            ONetItem.instrument_version_id == assessment.instrument_version_id,
            ONetItem.is_active.is_(True),
        )
        .order_by(ONetItem.item_index.asc())
    ).scalars().all()

    if len(items) != EXPECTED_TOTAL_ITEMS:
        raise AssessmentConflictError(
            "El instrumento activo no contiene exactamente 60 preguntas."
        )

    return [
        {
            "id": str(item.id),
            "code": item.item_code,
            "index": item.item_index,
            "text": item.question_text,
        }
        for item in items
    ]


def register_onet_response(
    *,
    session_id: uuid.UUID | str,
    item_id: uuid.UUID | str,
    response_raw: int,
    response_time_ms: int | None = None,
    tts_used: bool = False,
) -> ONetResponse:
    """Inserta o actualiza una respuesta oficial con comportamiento UPSERT."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError(
            "No se pueden modificar respuestas de una evaluación finalizada."
        )

    if isinstance(response_raw, bool) or not isinstance(response_raw, int):
        raise AssessmentValidationError("La respuesta debe ser un entero 1-5.")
    if not 1 <= response_raw <= 5:
        raise AssessmentValidationError("La respuesta debe estar entre 1 y 5.")
    if response_time_ms is not None and (
        isinstance(response_time_ms, bool)
        or not isinstance(response_time_ms, int)
        or response_time_ms < 0
    ):
        raise AssessmentValidationError(
            "response_time_ms debe ser un entero mayor o igual a cero."
        )

    parsed_item_id = _as_uuid(item_id, "item_id")
    item = db.session.get(ONetItem, parsed_item_id)
    if item is None or item.instrument_version_id != assessment.instrument_version_id:
        raise AssessmentValidationError(
            "La pregunta no pertenece al instrumento de esta evaluación."
        )

    response = db.session.execute(
        select(ONetResponse).where(
            ONetResponse.session_id == assessment.id,
            ONetResponse.item_id == item.id,
        )
    ).scalar_one_or_none()

    if response is None:
        response = ONetResponse(
            session_id=assessment.id,
            item_id=item.id,
            response_raw=response_raw,
            response_time_ms=response_time_ms,
            tts_used=bool(tts_used),
        )
        db.session.add(response)
    else:
        if response.response_raw != response_raw:
            response.changed_count += 1
        response.response_raw = response_raw
        response.response_time_ms = response_time_ms
        response.tts_used = response.tts_used or bool(tts_used)

    assessment.status = "in_progress"
    assessment.current_stage = "onet"
    assessment.current_item_index = item.item_index

    _commit()
    return response


def get_progress(session_id: uuid.UUID | str) -> dict[str, Any]:
    """Calcula el progreso oficial de las 60 respuestas O*NET."""

    assessment = get_assessment(session_id)
    answered = db.session.execute(
        select(func.count(ONetResponse.id)).where(
            ONetResponse.session_id == assessment.id
        )
    ).scalar_one()

    answered_int = int(answered)
    missing = max(EXPECTED_TOTAL_ITEMS - answered_int, 0)
    percentage = round((answered_int / EXPECTED_TOTAL_ITEMS) * 100, 2)

    return {
        "session_id": str(assessment.id),
        "status": assessment.status,
        "stage": assessment.current_stage,
        "current_item_index": assessment.current_item_index,
        "answered_items": answered_int,
        "missing_items": missing,
        "total_items": EXPECTED_TOTAL_ITEMS,
        "percentage": percentage,
        "onet_complete": answered_int == EXPECTED_TOTAL_ITEMS,
    }


def update_assessment_state(
    *,
    session_id: uuid.UUID | str,
    stage: str | None = None,
    current_item_index: int | None = None,
) -> AssessmentSession:
    """Actualiza el estado recuperable usado posteriormente por autosave."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError(
            "No se puede actualizar el estado de una sesión finalizada."
        )

    if stage is not None:
        stage = stage.strip().lower()
        if stage not in VALID_STAGES - {"completed"}:
            raise AssessmentValidationError("Etapa de evaluación no válida.")
        assessment.current_stage = stage

    if current_item_index is not None:
        if (
            isinstance(current_item_index, bool)
            or not isinstance(current_item_index, int)
        ):
            raise AssessmentValidationError("current_item_index debe ser entero.")
        if not 1 <= current_item_index <= EXPECTED_TOTAL_ITEMS:
            raise AssessmentValidationError(
                "current_item_index debe estar entre 1 y 60."
            )
        assessment.current_item_index = current_item_index

    if assessment.status == "created":
        assessment.status = "in_progress"

    _commit()
    return assessment


def register_interest_response(
    *,
    session_id: uuid.UUID | str,
    item_code: str,
    response_value: int,
) -> InterestResponse:
    """Guarda o actualiza una respuesta G01-G12."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError("La evaluación ya está cerrada.")
    if isinstance(response_value, bool) or not isinstance(response_value, int):
        raise AssessmentValidationError("La respuesta G debe ser entera 1-5.")
    if not 1 <= response_value <= 5:
        raise AssessmentValidationError("La respuesta G debe estar entre 1 y 5.")

    code = _clean_text(item_code, required=True)
    assert code is not None
    code = code.upper()
    if code not in INTEREST_CODES:
        raise AssessmentValidationError(
            "El ítem de interés debe estar entre G01 y G12."
        )

    item = db.session.execute(
        select(InterestItem).where(
            InterestItem.code == code,
            InterestItem.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if item is None:
        raise AssessmentValidationError(f"No existe el ítem de interés {code!r}.")

    response = db.session.execute(
        select(InterestResponse).where(
            InterestResponse.session_id == assessment.id,
            InterestResponse.interest_item_id == item.id,
        )
    ).scalar_one_or_none()

    if response is None:
        response = InterestResponse(
            session_id=assessment.id,
            interest_item_id=item.id,
            response_value=response_value,
        )
        db.session.add(response)
    else:
        response.response_value = response_value

    assessment.current_stage = "interests"
    assessment.status = "in_progress"
    _commit()
    return response


def replace_subject_selections(
    *,
    session_id: uuid.UUID | str,
    subject_codes: Iterable[str],
    other_text: str | None = None,
) -> list[SessionSubject]:
    """Reemplaza atómicamente la selección de materias (máximo tres)."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError("La evaluación ya está cerrada.")

    codes = [str(code).strip().lower() for code in subject_codes if str(code).strip()]
    unique_codes = list(dict.fromkeys(codes))
    if len(unique_codes) > MAX_SUBJECTS:
        raise AssessmentValidationError("Solo se pueden seleccionar hasta 3 materias.")
    if not unique_codes:
        raise AssessmentValidationError("Debe seleccionar al menos una materia.")

    subjects = db.session.execute(
        select(Subject).where(
            Subject.code.in_(unique_codes),
            Subject.is_active.is_(True),
        )
    ).scalars().all()
    if len(subjects) != len(unique_codes):
        found = {subject.code for subject in subjects}
        missing = sorted(set(unique_codes) - found)
        raise AssessmentValidationError(
            f"Materias inexistentes o inactivas: {', '.join(missing)}."
        )

    other_subject = next(
        (subject for subject in subjects if subject.code == "otra"),
        None,
    )
    normalized_other = _clean_text(other_text)
    if other_subject and other_subject.allows_other_text and not normalized_other:
        raise AssessmentValidationError(
            "Debe indicar cuál es la otra materia seleccionada."
        )

    db.session.query(SessionSubject).filter(
        SessionSubject.session_id == assessment.id
    ).delete(synchronize_session=False)

    links: list[SessionSubject] = []
    for subject in subjects:
        link = SessionSubject(
            session_id=assessment.id,
            subject_id=subject.id,
            other_text=(
                normalized_other
                if subject.allows_other_text
                else None
            ),
        )
        db.session.add(link)
        links.append(link)

    assessment.current_stage = "subjects"
    assessment.status = "in_progress"
    _commit()
    return links


def replace_activity_selections(
    *,
    session_id: uuid.UUID | str,
    activity_codes: Iterable[str],
    other_text: str | None = None,
) -> list[SessionActivity]:
    """Reemplaza actividades y aplica la regla de opción exclusiva 'ninguna'."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError("La evaluación ya está cerrada.")

    codes = [str(code).strip().lower() for code in activity_codes if str(code).strip()]
    unique_codes = list(dict.fromkeys(codes))
    if not unique_codes:
        raise AssessmentValidationError("Debe seleccionar al menos una actividad.")

    activities = db.session.execute(
        select(Activity).where(
            Activity.code.in_(unique_codes),
            Activity.is_active.is_(True),
        )
    ).scalars().all()
    if len(activities) != len(unique_codes):
        found = {activity.code for activity in activities}
        missing = sorted(set(unique_codes) - found)
        raise AssessmentValidationError(
            f"Actividades inexistentes o inactivas: {', '.join(missing)}."
        )

    if len(activities) > 1 and any(activity.is_exclusive for activity in activities):
        raise AssessmentValidationError(
            "La opción 'ninguna' no puede combinarse con otras actividades."
        )

    normalized_other = _clean_text(other_text)
    other_activity = next(
        (activity for activity in activities if activity.allows_other_text),
        None,
    )
    if other_activity and not normalized_other:
        raise AssessmentValidationError(
            "Debe describir la actividad seleccionada como 'otra'."
        )

    db.session.query(SessionActivity).filter(
        SessionActivity.session_id == assessment.id
    ).delete(synchronize_session=False)

    links: list[SessionActivity] = []
    for activity in activities:
        link = SessionActivity(
            session_id=assessment.id,
            activity_id=activity.id,
            other_text=(normalized_other if activity.allows_other_text else None),
        )
        db.session.add(link)
        links.append(link)

    assessment.current_stage = "activities"
    assessment.status = "in_progress"
    _commit()
    return links


def save_open_response(
    *,
    session_id: uuid.UUID | str,
    prompt_code: str,
    response_text: str,
) -> OpenResponse:
    """Guarda T01-T03 preservando el texto original del estudiante."""

    assessment = get_assessment(session_id)
    if assessment.status in {"completed", "abandoned"}:
        raise AssessmentConflictError("La evaluación ya está cerrada.")

    code = _clean_text(prompt_code, required=True)
    assert code is not None
    code = code.upper()
    if code not in {"T01", "T02", "T03"}:
        raise AssessmentValidationError("prompt_code debe ser T01, T02 o T03.")

    text = _clean_text(response_text, required=True)
    assert text is not None
    word_count = len(text.split())

    response = db.session.execute(
        select(OpenResponse).where(
            OpenResponse.session_id == assessment.id,
            OpenResponse.prompt_code == code,
        )
    ).scalar_one_or_none()

    if response is None:
        response = OpenResponse(
            session_id=assessment.id,
            prompt_code=code,
            response_text=text,
            word_count=word_count,
        )
        db.session.add(response)
    else:
        response.response_text = text
        response.word_count = word_count

    assessment.current_stage = "open_questions"
    assessment.status = "in_progress"
    _commit()
    return response



def get_onet_response_values(
    session_id: uuid.UUID | str,
) -> dict[str, int]:
    """Devuelve las respuestas O*NET existentes indexadas por UUID de ítem."""

    assessment = get_assessment(session_id)
    rows = db.session.execute(
        select(ONetResponse).where(
            ONetResponse.session_id == assessment.id
        )
    ).scalars().all()

    return {
        str(response.item_id): response.response_raw
        for response in rows
    }


def get_interest_form_state(
    session_id: uuid.UUID | str,
) -> dict[str, Any]:
    """Recupera G01-G12, materias y actividades para reanudar el formulario."""

    assessment = get_assessment(session_id)

    interest_rows = db.session.execute(
        select(InterestResponse)
        .where(InterestResponse.session_id == assessment.id)
    ).scalars().all()

    subject_rows = db.session.execute(
        select(SessionSubject)
        .where(SessionSubject.session_id == assessment.id)
    ).scalars().all()

    activity_rows = db.session.execute(
        select(SessionActivity)
        .where(SessionActivity.session_id == assessment.id)
    ).scalars().all()

    subject_other = next(
        (
            link.other_text
            for link in subject_rows
            if link.subject.allows_other_text and link.other_text
        ),
        "",
    )
    activity_other = next(
        (
            link.other_text
            for link in activity_rows
            if link.activity.allows_other_text and link.other_text
        ),
        "",
    )

    return {
        "interest_values": {
            response.item.code: response.response_value
            for response in interest_rows
        },
        "subject_codes": [link.subject.code for link in subject_rows],
        "subject_other": subject_other,
        "activity_codes": [link.activity.code for link in activity_rows],
        "activity_other": activity_other,
    }


def get_open_response_values(
    session_id: uuid.UUID | str,
) -> dict[str, str]:
    """Recupera T01-T03 para permitir reanudar el formulario abierto."""

    assessment = get_assessment(session_id)
    rows = db.session.execute(
        select(OpenResponse).where(
            OpenResponse.session_id == assessment.id
        )
    ).scalars().all()

    return {
        response.prompt_code: response.response_text
        for response in rows
    }

def finalize_assessment(session_id: uuid.UUID | str) -> AssessmentSession:
    """Valida el test, calcula RIASEC y cierra la sesión de forma atómica."""

    assessment = get_assessment(session_id)
    if assessment.status == "completed":
        return assessment
    if assessment.status == "abandoned":
        raise AssessmentConflictError(
            "Una evaluación abandonada no puede finalizarse directamente."
        )

    progress = get_progress(assessment.id)
    if not progress["onet_complete"]:
        raise AssessmentValidationError(
            "No se puede finalizar: faltan respuestas del instrumento O*NET."
        )

    interest_count = db.session.execute(
        select(func.count(InterestResponse.id)).where(
            InterestResponse.session_id == assessment.id
        )
    ).scalar_one()
    if int(interest_count) != 12:
        raise AssessmentValidationError(
            "No se puede finalizar: deben responderse las 12 preguntas "
            "de gustos actuales."
        )

    subject_count = db.session.execute(
        select(func.count()).select_from(SessionSubject).where(
            SessionSubject.session_id == assessment.id
        )
    ).scalar_one()
    if int(subject_count) < 1:
        raise AssessmentValidationError(
            "No se puede finalizar: faltan las materias favoritas."
        )

    activity_count = db.session.execute(
        select(func.count()).select_from(SessionActivity).where(
            SessionActivity.session_id == assessment.id
        )
    ).scalar_one()
    if int(activity_count) < 1:
        raise AssessmentValidationError(
            "No se puede finalizar: faltan las actividades actuales."
        )

    # T01 y T02 son obligatorias; T03 permanece opcional según el diccionario.
    open_codes = set(
        db.session.execute(
            select(OpenResponse.prompt_code).where(
                OpenResponse.session_id == assessment.id
            )
        ).scalars().all()
    )
    missing_required_texts = {"T01", "T02"} - open_codes
    if missing_required_texts:
        raise AssessmentValidationError(
            "No se puede finalizar: faltan respuestas abiertas obligatorias "
            f"({', '.join(sorted(missing_required_texts))})."
        )

    try:
        calculate_session_result(assessment, commit=False)
        now = utcnow()
        assessment.completed_at = now
        assessment.status = "completed"
        assessment.current_stage = "completed"
        assessment.duration_seconds = max(
            int((now - assessment.started_at).total_seconds()),
            0,
        )
        db.session.commit()
        return assessment
    except (RiasecScoringError, AssessmentServiceError):
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise



def purge_participant_data(participant_code: str) -> dict[str, int | str]:
    """Elimina de PostgreSQL los registros ligados a un código participante.

    Esta operación apoya retiro/depuración de datos dentro de la base activa.
    No afirma borrado físico de copias de seguridad, snapshots o almacenamiento
    administrado fuera de PostgreSQL; esos soportes requieren el procedimiento
    operativo de retención y destrucción del proyecto.
    """

    code = _clean_text(participant_code, required=True)
    assert code is not None
    code = code.upper()

    participant = db.session.execute(
        select(Participant).where(Participant.participant_code == code)
    ).scalar_one_or_none()
    if participant is None:
        raise AssessmentNotFoundError(
            "No existe un participante con el código indicado."
        )

    session_count = len(participant.assessment_sessions)
    consent_count = len(participant.consent_records)

    try:
        db.session.delete(participant)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "participant_code": code,
        "assessment_sessions_deleted": session_count,
        "consent_records_deleted": consent_count,
    }
