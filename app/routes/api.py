"""API REST de la plataforma RIASEC.

FASE 10-B — API y validaciones
------------------------------
Este módulo completa los endpoints del flujo de evaluación y estandariza las
respuestas JSON. Las rutas validan la forma de la solicitud, delegan las reglas
de negocio en Services y traducen errores de dominio a códigos HTTP claros.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from app.services.access_service import (
    ASSESSMENT_ACCESS_HEADER,
    AssessmentAccessError,
    bind_assessment_to_browser,
    issue_assessment_access_token,
    require_assessment_access,
)
from app.services.assessment_service import (
    CURRENT_CONSENT_VERSION,
    DEFAULT_INSTRUMENT_VERSION,
    AssessmentConflictError,
    AssessmentNotFoundError,
    AssessmentServiceError,
    AssessmentValidationError,
    create_assessment,
    finalize_assessment,
    get_assessment,
    get_progress,
    get_questions,
    register_interest_response,
    register_onet_response,
    replace_activity_selections,
    replace_subject_selections,
    save_open_response,
    update_assessment_state,
)
from app.services.catalog_service import get_public_catalogs
from app.services.riasec_service import (
    RiasecScoringError,
    serialize_persisted_result,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

ONET_ANSWER_OPTIONS = (
    {"value": 1, "name": "Me disgusta mucho"},
    {"value": 2, "name": "Me disgusta"},
    {"value": 3, "name": "No estoy seguro"},
    {"value": 4, "name": "Me gusta"},
    {"value": 5, "name": "Me gusta mucho"},
)


class ApiRequestError(ValueError):
    """La solicitud HTTP no tiene la estructura esperada por la API."""


def _success(
    data: Any,
    message: str,
    status_code: int = 200,
):
    """Construye una respuesta JSON exitosa con formato uniforme."""

    return (
        jsonify(
            {
                "success": True,
                "data": data,
                "message": message,
            }
        ),
        status_code,
    )


def _error(message: str, status_code: int):
    """Construye una respuesta JSON de error con formato uniforme."""

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


def _service_error_response(error: Exception):
    """Traduce excepciones controladas a códigos HTTP de la API."""

    if isinstance(error, ApiRequestError):
        return _error(str(error), 400)
    if isinstance(error, AssessmentAccessError):
        return _error("No autorizado para esta evaluación.", 403)
    if isinstance(error, AssessmentNotFoundError):
        return _error(str(error), 404)
    if isinstance(error, AssessmentConflictError):
        return _error(str(error), 409)
    if isinstance(error, (AssessmentValidationError, RiasecScoringError)):
        return _error(str(error), 422)
    if isinstance(error, AssessmentServiceError):
        return _error(str(error), 400)

    current_app.logger.exception("Error no controlado en API RIASEC.")
    return _error("Ocurrió un error interno inesperado.", 500)


def _payload() -> dict[str, Any]:
    """Obtiene un objeto JSON y diferencia errores HTTP de dominio."""

    if not request.is_json:
        raise ApiRequestError(
            "La solicitud debe utilizar Content-Type application/json."
        )

    data = request.get_json(silent=True)
    if data is None:
        raise ApiRequestError("El cuerpo JSON está vacío o no es válido.")
    if not isinstance(data, dict):
        raise ApiRequestError("El cuerpo JSON debe ser un objeto.")
    return data


def _required(data: Mapping[str, Any], key: str) -> Any:
    """Recupera un campo obligatorio sin convertir silenciosamente su tipo."""

    if key not in data:
        raise ApiRequestError(f"Falta el campo obligatorio '{key}'.")
    return data[key]


def _required_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = _required(data, key)
    if not isinstance(value, Mapping):
        raise ApiRequestError(f"'{key}' debe ser un objeto JSON.")
    return value


def _required_list(data: Mapping[str, Any], key: str) -> list[Any]:
    value = _required(data, key)
    if not isinstance(value, list):
        raise ApiRequestError(f"'{key}' debe ser una lista JSON.")
    return value


def _required_bool(data: Mapping[str, Any], key: str) -> bool:
    value = _required(data, key)
    if not isinstance(value, bool):
        raise ApiRequestError(f"'{key}' debe ser booleano.")
    return value


def _optional_bool(
    data: Mapping[str, Any],
    key: str,
    *,
    default: bool = False,
) -> bool:
    if key not in data:
        return default
    value = data[key]
    if not isinstance(value, bool):
        raise ApiRequestError(f"'{key}' debe ser booleano.")
    return value



@api_bp.get("/assessment")
def assessment_state():
    """GET /api/assessment?session_id=<uuid>."""

    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        return _error("Falta el parámetro session_id.", 400)

    try:
        require_assessment_access(session_id)
        assessment = get_assessment(session_id)
        progress = get_progress(session_id)
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "session_id": str(assessment.id),
            "participant_code": assessment.participant.participant_code,
            "status": assessment.status,
            "stage": assessment.current_stage,
            "current_item_index": assessment.current_item_index,
            "collection_phase": assessment.collection_phase,
            "progress": progress,
        },
        "Evaluación recuperada correctamente.",
    )


@api_bp.get("/assessment/questions")
def assessment_questions():
    """Devuelve las 60 preguntas sin exponer la dimensión RIASEC interna."""

    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        return _error("Falta el parámetro session_id.", 400)

    try:
        require_assessment_access(session_id)
        questions = get_questions(session_id)
        progress = get_progress(session_id)
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "questions": questions,
            "answer_options": list(ONET_ANSWER_OPTIONS),
            "progress": progress,
        },
        "Preguntas recuperadas correctamente.",
    )


@api_bp.post("/assessment/start")
def assessment_start():
    """Crea participante, consentimiento y sesión de evaluación."""

    try:
        data = _payload()
        demographics = _required_mapping(data, "demographics")
        consent = _required_mapping(data, "consent")

        accepted = _required_bool(consent, "accepted")
        data_authorization = _required_bool(consent, "data_authorization")
        consent_version = str(_required(consent, "version")).strip()

        if accepted is not True:
            raise AssessmentValidationError(
                "El consentimiento informado debe estar aceptado."
            )
        if data_authorization is not True:
            raise AssessmentValidationError(
                "Se requiere autorización para el uso académico de los datos."
            )
        assent_accepted = consent.get("assent_accepted")
        if assent_accepted is not None and not isinstance(
            assent_accepted,
            bool,
        ):
            raise ApiRequestError("'assent_accepted' debe ser booleano o null.")

        assessment = create_assessment(
            demographics=demographics,
            consent_version=consent_version,
            consent_accepted=True,
            assent_accepted=assent_accepted,
            guardian_consent_required=_optional_bool(
                consent,
                "guardian_consent_required",
            ),
            guardian_consent_reference=consent.get(
                "guardian_consent_reference"
            ),
            collection_method=str(consent.get("collection_method", "digital")),
            instrument_version_code=DEFAULT_INSTRUMENT_VERSION,
        )
        bind_assessment_to_browser(assessment.id)
        access_token = issue_assessment_access_token(assessment.id)
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "session_id": str(assessment.id),
            "participant_code": assessment.participant.participant_code,
            "access_token": access_token,
            "access_header": ASSESSMENT_ACCESS_HEADER,
            "status": assessment.status,
            "stage": assessment.current_stage,
            "current_item_index": assessment.current_item_index,
            "collection_phase": assessment.collection_phase,
            "consent_version": CURRENT_CONSENT_VERSION,
        },
        "Evaluación iniciada correctamente.",
        201,
    )


@api_bp.post("/assessment/response")
def assessment_response():
    """Guarda o actualiza una respuesta O*NET 1-5."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        response = register_onet_response(
            session_id=session_id,
            item_id=_required(data, "item_id"),
            response_raw=_required(data, "response_raw"),
            response_time_ms=data.get("response_time_ms"),
            tts_used=_optional_bool(data, "tts_used"),
        )
        progress = get_progress(data["session_id"])
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "response_id": str(response.id),
            "response_raw": response.response_raw,
            "response_score": response.response_score,
            "changed_count": response.changed_count,
            "tts_used": response.tts_used,
            "progress": progress,
        },
        "Respuesta guardada correctamente.",
    )


@api_bp.post("/assessment/autosave")
def assessment_autosave():
    """Guarda etapa e índice actual para recuperación de navegación."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        assessment = update_assessment_state(
            session_id=session_id,
            stage=data.get("stage"),
            current_item_index=data.get("current_item_index"),
        )
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "session_id": str(assessment.id),
            "status": assessment.status,
            "stage": assessment.current_stage,
            "current_item_index": assessment.current_item_index,
        },
        "Estado guardado correctamente.",
    )


@api_bp.post("/assessment/interest-response")
def assessment_interest_response():
    """Guarda una respuesta propia G01-G12."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        response = register_interest_response(
            session_id=session_id,
            item_code=str(_required(data, "item_code")),
            response_value=_required(data, "response_value"),
        )
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "response_id": str(response.id),
            "item_code": response.item.code,
            "response_value": response.response_value,
        },
        "Interés guardado correctamente.",
    )


@api_bp.post("/assessment/subjects")
def assessment_subjects():
    """Reemplaza la selección actual de materias favoritas."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        links = replace_subject_selections(
            session_id=session_id,
            subject_codes=_required_list(data, "subject_codes"),
            other_text=data.get("other_text"),
        )
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "subject_codes": [link.subject.code for link in links],
        },
        "Materias guardadas correctamente.",
    )


@api_bp.post("/assessment/activities")
def assessment_activities():
    """Reemplaza la selección actual de actividades extracurriculares."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        links = replace_activity_selections(
            session_id=session_id,
            activity_codes=_required_list(data, "activity_codes"),
            other_text=data.get("other_text"),
        )
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "activity_codes": [link.activity.code for link in links],
        },
        "Actividades guardadas correctamente.",
    )


@api_bp.post("/assessment/open-response")
def assessment_open_response():
    """Guarda T01, T02 o T03 sin alterar el texto original."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        response = save_open_response(
            session_id=session_id,
            prompt_code=str(_required(data, "prompt_code")),
            response_text=_required(data, "response_text"),
        )
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "response_id": str(response.id),
            "prompt_code": response.prompt_code,
            "word_count": response.word_count,
        },
        "Respuesta abierta guardada correctamente.",
    )


@api_bp.post("/assessment/complete")
def assessment_complete():
    """Valida la evaluación completa, calcula RIASEC y cierra la sesión."""

    try:
        data = _payload()
        session_id = _required(data, "session_id")
        require_assessment_access(session_id)
        assessment = finalize_assessment(session_id)
    except Exception as exc:
        return _service_error_response(exc)

    return _success(
        {
            "session_id": str(assessment.id),
            "status": assessment.status,
            "result": serialize_persisted_result(assessment),
        },
        "Evaluación finalizada correctamente.",
    )


@api_bp.get("/results/<uuid:session_id>")
def api_results(session_id: uuid.UUID):
    """Recupera el resultado persistido de una sesión finalizada."""

    try:
        require_assessment_access(session_id)
        assessment = get_assessment(session_id)
    except Exception as exc:
        return _service_error_response(exc)

    if assessment.riasec_result is None:
        return _error("La evaluación todavía no tiene resultado RIASEC.", 409)

    try:
        result = serialize_persisted_result(assessment)
    except Exception as exc:
        return _service_error_response(exc)

    return _success(result, "Resultado recuperado correctamente.")


@api_bp.get("/catalogs")
def catalogs():
    """Devuelve catálogos públicos requeridos por el flujo."""

    try:
        data = get_public_catalogs()
    except Exception:
        current_app.logger.exception("No fue posible recuperar catálogos.")
        return _error("No fue posible recuperar los catálogos.", 500)

    return _success(data, "Catálogos recuperados correctamente.")
