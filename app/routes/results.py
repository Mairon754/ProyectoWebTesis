"""Rutas web para presentar el resultado RIASEC.

FASE 11 — Resultados
--------------------
La ruta recupera el resultado persistido y delega toda interpretación del
perfil en ``riasec_service``. La plantilla solo representa datos ya preparados
por el backend.
"""

from __future__ import annotations

import uuid

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.services.access_service import (
    AssessmentAccessError,
    require_assessment_access,
)
from app.services.assessment_service import (
    AssessmentNotFoundError,
    get_assessment,
)
from app.services.riasec_service import build_result_interpretation

results_bp = Blueprint(
    "results",
    __name__,
    url_prefix="/results",
)


@results_bp.before_request
def require_owned_result():
    """Protege resultados frente a acceso por UUID adivinado o compartido."""

    session_id = (request.view_args or {}).get("session_id")
    if session_id is None:
        return None
    try:
        require_assessment_access(session_id)
    except AssessmentAccessError:
        abort(403, description="No autorizado para este resultado.")
    return None


def _result_view_model(assessment) -> dict[str, object] | None:
    """Prepara la vista sin introducir cálculo RIASEC en la ruta."""

    result = assessment.riasec_result
    if result is None:
        return None

    interpretation = build_result_interpretation(result)

    return {
        "session_id": str(assessment.id),
        "participant_code": assessment.participant.participant_code,
        "holland_code": result.holland_code,
        "tie_top1": result.tie_top1,
        "top1_candidates": list(result.top1_candidates or []),
        "scoring_version": result.scoring_version,
        "calculated_at": result.calculated_at,
        **interpretation,
    }


@results_bp.get("/<uuid:session_id>")
def result_page(session_id: uuid.UUID):
    """Renderiza el resultado oficial de una evaluación finalizada."""

    try:
        assessment = get_assessment(session_id)
    except AssessmentNotFoundError as exc:
        return (
            render_template(
                "results.html",
                error=str(exc),
                result=None,
            ),
            404,
        )

    data = _result_view_model(assessment)
    if data is None:
        return redirect(
            url_for(
                "assessment.open_questions_page",
                session_id=session_id,
            )
        )

    return render_template(
        "results.html",
        result=data,
    )
