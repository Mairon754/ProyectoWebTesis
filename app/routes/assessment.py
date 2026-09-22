"""Rutas web del flujo de evaluación RIASEC.

FASE 5/7/8/9 — Flujo, navegación, TTS y metadatos de autosave
------------------------------------------------------
La capa web renderiza formularios y delega validaciones, persistencia y
cálculos a los servicios. En Fase 7 acepta una dirección de navegación para
que swipe hacia arriba avance y swipe hacia abajo regrese sin perder una
respuesta seleccionada. En Fase 8 también recibe el metadato ``tts_used``
generado por el lector del frontend. Autosave JS continúa reservado para Fase 9.
"""

from __future__ import annotations

import uuid

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.services.assessment_service import (
    AssessmentConflictError,
    AssessmentNotFoundError,
    AssessmentServiceError,
    AssessmentValidationError,
    finalize_assessment,
    get_assessment,
    get_interest_form_state,
    get_onet_response_values,
    get_open_response_values,
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
from app.services.riasec_service import RiasecScoringError

assessment_bp = Blueprint(
    "assessment",
    __name__,
    url_prefix="/assessment",
)

ONET_ANSWER_OPTIONS = (
    (1, "Me disgusta mucho"),
    (2, "Me disgusta"),
    (3, "No estoy seguro"),
    (4, "Me gusta"),
    (5, "Me gusta mucho"),
)

OPEN_PROMPTS = {
    "T01": (
        "Si tuvieras una tarde completamente libre y pudieras dedicarla a "
        "cualquier actividad que te guste, ¿qué elegirías hacer y por qué?"
    ),
    "T02": (
        "Cuéntanos sobre una actividad, proyecto, tarea o experiencia que "
        "hayas disfrutado mucho. Explica qué hiciste y qué fue lo que más "
        "te gustó."
    ),
    "T03": (
        "Imagina que en algunos años estás realizando un trabajo o actividad "
        "que realmente disfrutas. ¿Qué te gustaría estar haciendo?"
    ),
}


def _status_code(error: Exception) -> int:
    if isinstance(error, AssessmentNotFoundError):
        return 404
    if isinstance(error, AssessmentConflictError):
        return 409
    if isinstance(error, AssessmentValidationError):
        return 422
    return 400


def _service_error_template(
    *,
    template_name: str,
    error: Exception,
    status_code: int | None = None,
    **context,
):
    """Renderiza un error de dominio sin exponer trazas al usuario."""

    return (
        render_template(
            template_name,
            error=str(error),
            **context,
        ),
        status_code or _status_code(error),
    )


def _safe_question_index(raw_value: str | None, fallback: int) -> int:
    try:
        value = int(raw_value) if raw_value is not None else fallback
    except (TypeError, ValueError):
        value = fallback
    return min(max(value, 1), 60)


def _first_missing_question(
    questions: list[dict[str, object]],
    answers: dict[str, int],
) -> int | None:
    for question in questions:
        if str(question["id"]) not in answers:
            return int(question["index"])
    return None


@assessment_bp.get("/<uuid:session_id>")
def assessment_page(session_id: uuid.UUID):
    """Muestra una pregunta O*NET por solicitud HTTP."""

    try:
        assessment = get_assessment(session_id)
        if assessment.status == "completed":
            return redirect(
                url_for("results.result_page", session_id=session_id)
            )

        questions = get_questions(session_id)
        answers = get_onet_response_values(session_id)
        progress = get_progress(session_id)
    except AssessmentServiceError as exc:
        return _service_error_template(
            template_name="assessment.html",
            error=exc,
            assessment=None,
            question=None,
            progress=None,
            answer_options=ONET_ANSWER_OPTIONS,
            selected_value=None,
            previous_index=None,
        )

    fallback = assessment.current_item_index or 1
    index = _safe_question_index(request.args.get("q"), fallback)
    question = questions[index - 1]

    try:
        update_assessment_state(
            session_id=session_id,
            stage="onet",
            current_item_index=index,
        )
    except AssessmentServiceError:
        # La página sigue siendo renderizable aunque falle un autosave de
        # navegación; el guardado de la respuesta sí se valida estrictamente.
        current_app.logger.exception(
            "No fue posible actualizar el índice de navegación O*NET."
        )

    selected_value = answers.get(str(question["id"]))

    return render_template(
        "assessment.html",
        assessment=assessment,
        question=question,
        progress=progress,
        answer_options=ONET_ANSWER_OPTIONS,
        selected_value=selected_value,
        previous_index=(index - 1 if index > 1 else None),
    )


@assessment_bp.post("/<uuid:session_id>/answer")
def answer_question(session_id: uuid.UUID):
    """Guarda una respuesta y avanza a la siguiente pregunta pendiente."""

    try:
        current_index = int(request.form.get("question_index", "1"))
        response_raw = int(request.form["response_raw"])
        item_id = request.form["item_id"]
        tts_used = request.form.get("tts_used", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        response_time_raw = request.form.get("response_time_ms", "").strip()
        response_time_ms = (
            int(response_time_raw)
            if response_time_raw
            else None
        )

        navigation_direction = request.form.get(
            "navigation_direction",
            "next",
        )
        if navigation_direction not in {"next", "previous"}:
            raise ValueError("Dirección de navegación no válida.")

        register_onet_response(
            session_id=session_id,
            item_id=item_id,
            response_raw=response_raw,
            response_time_ms=response_time_ms,
            tts_used=tts_used,
        )

        if navigation_direction == "previous" and current_index > 1:
            return redirect(
                url_for(
                    "assessment.assessment_page",
                    session_id=session_id,
                    q=current_index - 1,
                )
            )

        questions = get_questions(session_id)
        answers = get_onet_response_values(session_id)
        progress = get_progress(session_id)

        if current_index < 60:
            return redirect(
                url_for(
                    "assessment.assessment_page",
                    session_id=session_id,
                    q=current_index + 1,
                )
            )

        if progress["onet_complete"]:
            update_assessment_state(
                session_id=session_id,
                stage="interests",
                current_item_index=60,
            )
            return redirect(
                url_for("assessment.interests_page", session_id=session_id)
            )

        missing_index = _first_missing_question(questions, answers)
        flash(
            "Aún falta responder alguna pregunta. Te llevamos a la primera "
            "que está pendiente.",
            "warning",
        )
        return redirect(
            url_for(
                "assessment.assessment_page",
                session_id=session_id,
                q=missing_index or 1,
            )
        )
    except KeyError:
        flash("Selecciona una opción antes de continuar.", "warning")
        return redirect(
            url_for(
                "assessment.assessment_page",
                session_id=session_id,
                q=request.form.get("question_index", 1),
            )
        )
    except (TypeError, ValueError):
        flash("La respuesta enviada no es válida.", "error")
        return redirect(
            url_for("assessment.assessment_page", session_id=session_id)
        )
    except AssessmentServiceError as exc:
        flash(str(exc), "error")
        return redirect(
            url_for("assessment.assessment_page", session_id=session_id)
        )


@assessment_bp.route("/<uuid:session_id>/interests", methods=["GET", "POST"])
def interests_page(session_id: uuid.UUID):
    """Recoge G01-G12, materias favoritas y actividades actuales."""

    try:
        assessment = get_assessment(session_id)
        if assessment.status == "completed":
            return redirect(
                url_for("results.result_page", session_id=session_id)
            )

        catalogs = get_public_catalogs()
        saved_state = get_interest_form_state(session_id)
    except AssessmentServiceError as exc:
        return _service_error_template(
            template_name="interests.html",
            error=exc,
            assessment=None,
            catalogs={
                "interests": [],
                "subjects": [],
                "activities": [],
                "interest_answer_options": [],
            },
            state={},
        )

    if request.method == "POST":
        try:
            for item in catalogs["interests"]:
                field_name = item["code"]
                if field_name not in request.form:
                    raise AssessmentValidationError(
                        "Debes responder las 12 preguntas de gustos actuales."
                    )
                register_interest_response(
                    session_id=session_id,
                    item_code=field_name,
                    response_value=int(request.form[field_name]),
                )

            replace_subject_selections(
                session_id=session_id,
                subject_codes=request.form.getlist("subject_codes"),
                other_text=request.form.get("subject_other"),
            )

            replace_activity_selections(
                session_id=session_id,
                activity_codes=request.form.getlist("activity_codes"),
                other_text=request.form.get("activity_other"),
            )

            update_assessment_state(
                session_id=session_id,
                stage="open_questions",
                current_item_index=60,
            )

            return redirect(
                url_for(
                    "assessment.open_questions_page",
                    session_id=session_id,
                )
            )
        except (ValueError, AssessmentServiceError) as exc:
            state = {
                "interest_values": {
                    item["code"]: request.form.get(item["code"])
                    for item in catalogs["interests"]
                },
                "subject_codes": request.form.getlist("subject_codes"),
                "subject_other": request.form.get("subject_other", ""),
                "activity_codes": request.form.getlist("activity_codes"),
                "activity_other": request.form.get("activity_other", ""),
            }
            return _service_error_template(
                template_name="interests.html",
                error=(
                    exc
                    if isinstance(exc, AssessmentServiceError)
                    else AssessmentValidationError(
                        "Las respuestas de gustos deben estar entre 1 y 5."
                    )
                ),
                assessment=assessment,
                catalogs=catalogs,
                state=state,
            )

    return render_template(
        "interests.html",
        assessment=assessment,
        catalogs=catalogs,
        state=saved_state,
    )


@assessment_bp.route(
    "/<uuid:session_id>/open-questions",
    methods=["GET", "POST"],
)
def open_questions_page(session_id: uuid.UUID):
    """Recoge T01-T03 y finaliza la evaluación."""

    try:
        assessment = get_assessment(session_id)
        if assessment.status == "completed":
            return redirect(
                url_for("results.result_page", session_id=session_id)
            )
        saved_values = get_open_response_values(session_id)
    except AssessmentServiceError as exc:
        return _service_error_template(
            template_name="open_questions.html",
            error=exc,
            assessment=None,
            prompts=OPEN_PROMPTS,
            values={},
        )

    if request.method == "POST":
        values = {
            "T01": request.form.get("T01", "").strip(),
            "T02": request.form.get("T02", "").strip(),
            "T03": request.form.get("T03", "").strip(),
        }

        try:
            save_open_response(
                session_id=session_id,
                prompt_code="T01",
                response_text=values["T01"],
            )
            save_open_response(
                session_id=session_id,
                prompt_code="T02",
                response_text=values["T02"],
            )
            if values["T03"]:
                save_open_response(
                    session_id=session_id,
                    prompt_code="T03",
                    response_text=values["T03"],
                )

            finalize_assessment(session_id)
            return redirect(
                url_for("results.result_page", session_id=session_id)
            )
        except (
            AssessmentServiceError,
            RiasecScoringError,
        ) as exc:
            return _service_error_template(
                template_name="open_questions.html",
                error=exc,
                assessment=assessment,
                prompts=OPEN_PROMPTS,
                values=values,
            )
        except Exception:
            current_app.logger.exception(
                "No fue posible finalizar la evaluación desde el flujo web."
            )
            return (
                render_template(
                    "open_questions.html",
                    error=(
                        "No fue posible finalizar la evaluación. Intenta de "
                        "nuevo o revisa los registros del servidor."
                    ),
                    assessment=assessment,
                    prompts=OPEN_PROMPTS,
                    values=values,
                ),
                500,
            )

    return render_template(
        "open_questions.html",
        assessment=assessment,
        prompts=OPEN_PROMPTS,
        values=saved_values,
    )
