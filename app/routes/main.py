"""Rutas web generales de la plataforma RIASEC.

FASE 5 + FASE 10 — Flujo y consentimiento informado
------------------------------------------------------
Estas rutas implementan bienvenida, consentimiento y datos demográficos.
La Fase 10 versiona el consentimiento legal y exige la autorización de uso
académico antes de crear la evaluación. La lógica de creación continúa
delegada al servicio de dominio.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import text

from app.extensions import db
from app.services.assessment_service import (
    CURRENT_CONSENT_VERSION,
    AssessmentServiceError,
    create_assessment,
)
from app.services.catalog_service import get_catalog_status

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    """Renderiza la pantalla de bienvenida de la evaluación."""

    return render_template("welcome.html")


@main_bp.route("/consent", methods=["GET", "POST"])
def consent():
    """Recoge consentimiento/asentimiento básico antes de los datos."""

    if request.method == "POST":
        understood = request.form.get("understood") == "on"
        voluntary = request.form.get("voluntary") == "on"
        data_authorization = (
            request.form.get("data_authorization") == "on"
        )

        if not (understood and voluntary and data_authorization):
            return (
                render_template(
                    "consent.html",
                    error=(
                        "Debes confirmar que comprendiste la información, "
                        "que aceptas participar voluntariamente y que autorizas "
                        "el uso académico de los datos de la prueba piloto."
                    ),
                    understood=understood,
                    voluntary=voluntary,
                    data_authorization=data_authorization,
                ),
                422,
            )

        session["pending_consent"] = {
            "consent_version": CURRENT_CONSENT_VERSION,
            "consent_accepted": True,
            "assent_accepted": True,
            "guardian_consent_required": False,
            "guardian_consent_reference": None,
            "collection_method": "digital",
        }

        return redirect(url_for("main.demographics"))

    return render_template(
        "consent.html",
        understood=False,
        voluntary=False,
        data_authorization=False,
    )


@main_bp.route("/demographics", methods=["GET", "POST"])
def demographics():
    """Recoge datos mínimos y crea una sesión de evaluación."""

    pending_consent = session.get("pending_consent")
    if pending_consent is None:
        flash(
            "Primero debes revisar y aceptar la información de participación.",
            "warning",
        )
        return redirect(url_for("main.consent"))

    if request.method == "POST":
        demographics_data = {
            "age": request.form.get("age"),
            "grade": request.form.get("grade"),
            "institution_code": request.form.get("institution_code"),
            "municipality": request.form.get("municipality"),
            "zone": request.form.get("zone"),
            "gender_self_reported": (
                request.form.get("gender_self_reported") or None
            ),
            "has_career_in_mind": request.form.get("has_career_in_mind"),
            "career_in_mind_text": (
                request.form.get("career_in_mind_text") or None
            ),
            "device_type": "unknown",
        }

        try:
            assessment = create_assessment(
                demographics=demographics_data,
                **pending_consent,
            )
        except AssessmentServiceError as exc:
            return (
                render_template(
                    "demographics.html",
                    error=str(exc),
                    form=request.form,
                ),
                422,
            )
        except Exception:
            current_app.logger.exception(
                "No fue posible crear la evaluación desde el flujo web."
            )
            return (
                render_template(
                    "demographics.html",
                    error=(
                        "No fue posible iniciar la evaluación. Verifica que "
                        "PostgreSQL y los catálogos estén disponibles."
                    ),
                    form=request.form,
                ),
                500,
            )

        session.pop("pending_consent", None)
        session["active_assessment_id"] = str(assessment.id)

        return redirect(
            url_for(
                "assessment.assessment_page",
                session_id=assessment.id,
            )
        )

    return render_template("demographics.html", form={})


@main_bp.get("/health")
def health():
    """Comprueba conexión a PostgreSQL y disponibilidad de catálogos."""

    try:
        db.session.execute(text("SELECT 1"))
        catalog_status = get_catalog_status()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Fallo durante health check.")
        return (
            jsonify(
                {
                    "success": False,
                    "data": {"database": "unavailable"},
                    "message": "La base de datos no está disponible.",
                }
            ),
            503,
        )

    return jsonify(
        {
            "success": True,
            "data": {
                "database": "ok",
                "catalogs": catalog_status,
            },
            "message": "Servicio operativo.",
        }
    )
