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
from app.services.access_service import bind_assessment_to_browser
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
    """Recoge consentimiento adulto o asentimiento con referencia de acudiente."""

    collection_phase = current_app.config.get("COLLECTION_PHASE", "pilot")

    if request.method == "POST":
        age_group = (request.form.get("age_group") or "").strip()
        understood = request.form.get("understood") == "on"
        voluntary = request.form.get("voluntary") == "on"
        data_authorization = (
            request.form.get("data_authorization") == "on"
        )
        assent_accepted = request.form.get("assent_accepted") == "on"
        guardian_reference = (
            request.form.get("guardian_consent_reference") or ""
        ).strip()

        base_valid = (
            age_group in {"minor", "adult"}
            and understood
            and voluntary
            and data_authorization
        )
        minor_valid = (
            age_group != "minor"
            or (assent_accepted and len(guardian_reference) >= 6)
        )

        if not (base_valid and minor_valid):
            return (
                render_template(
                    "consent.html",
                    error=(
                        "No es posible continuar hasta completar las "
                        "confirmaciones éticas requeridas. Si eres menor de "
                        "18 años, tu acudiente debe haber autorizado previamente "
                        "tu participación y debes ingresar la referencia entregada "
                        "por la institución."
                    ),
                    age_group=age_group,
                    understood=understood,
                    voluntary=voluntary,
                    data_authorization=data_authorization,
                    assent_accepted=assent_accepted,
                    guardian_consent_reference=guardian_reference,
                    collection_phase=collection_phase,
                ),
                422,
            )

        is_minor = age_group == "minor"
        session["pending_consent"] = {
            "declared_age_group": age_group,
            "consent_version": CURRENT_CONSENT_VERSION,
            "consent_accepted": True,
            "assent_accepted": True if is_minor else None,
            "guardian_consent_required": is_minor,
            "guardian_consent_reference": (
                guardian_reference if is_minor else None
            ),
            "collection_method": "institutional" if is_minor else "digital",
        }

        return redirect(url_for("main.demographics"))

    return render_template(
        "consent.html",
        age_group="",
        understood=False,
        voluntary=False,
        data_authorization=False,
        assent_accepted=False,
        guardian_consent_reference="",
        collection_phase=collection_phase,
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

        consent_data = dict(pending_consent)
        declared_age_group = consent_data.pop("declared_age_group", None)
        try:
            age_value = int(demographics_data["age"])
        except (TypeError, ValueError):
            age_value = None

        if age_value is not None and declared_age_group:
            actual_age_group = "minor" if age_value < 18 else "adult"
            if actual_age_group != declared_age_group:
                return (
                    render_template(
                        "demographics.html",
                        error=(
                            "La edad indicada no coincide con la modalidad de "
                            "consentimiento seleccionada. Vuelve al consentimiento "
                            "y corrige la información antes de continuar."
                        ),
                        form=request.form,
                        collection_phase=current_app.config.get(
                            "COLLECTION_PHASE", "pilot"
                        ),
                        authorized_institutions=current_app.config.get(
                            "AUTHORIZED_INSTITUTION_CODES", ()
                        ),
                    ),
                    422,
                )

        try:
            assessment = create_assessment(
                demographics=demographics_data,
                **consent_data,
            )
        except AssessmentServiceError as exc:
            return (
                render_template(
                    "demographics.html",
                    error=str(exc),
                    form=request.form,
                    collection_phase=current_app.config.get(
                        "COLLECTION_PHASE", "pilot"
                    ),
                    authorized_institutions=current_app.config.get(
                        "AUTHORIZED_INSTITUTION_CODES", ()
                    ),
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
                    collection_phase=current_app.config.get(
                        "COLLECTION_PHASE", "pilot"
                    ),
                    authorized_institutions=current_app.config.get(
                        "AUTHORIZED_INSTITUTION_CODES", ()
                    ),
                ),
                500,
            )

        session.pop("pending_consent", None)
        bind_assessment_to_browser(assessment.id)

        return redirect(
            url_for(
                "assessment.assessment_page",
                session_id=assessment.id,
            )
        )

    return render_template(
        "demographics.html",
        form={},
        collection_phase=current_app.config.get("COLLECTION_PHASE", "pilot"),
        authorized_institutions=current_app.config.get(
            "AUTHORIZED_INSTITUTION_CODES", ()
        ),
    )


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
