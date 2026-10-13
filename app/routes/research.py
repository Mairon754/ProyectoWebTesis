"""Módulo privado para investigadores y exportación de datasets.

FASE 14 — Investigación
-----------------------
Este blueprint separa la experiencia del estudiante del acceso investigador.
La autenticación es deliberadamente sencilla: usuarios configurados mediante
variables de entorno y contraseñas almacenadas como hash Werkzeug.
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO
from typing import Any, Callable, TypeVar
from urllib.parse import urlencode

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import ResearchAuditEvent
from app.services.assessment_service import (
    AssessmentNotFoundError,
    get_assessment,
)
from app.services.dataset_service import (
    DatasetServiceError,
    RESEARCH_DATASET_KINDS,
    build_research_dataset,
    export_records_to_csv,
    export_records_to_xlsx,
    get_research_filter_options,
    get_research_sessions,
    get_research_summary,
    normalize_research_filters,
    review_session_quality,
)

research_bp = Blueprint(
    "research",
    __name__,
    url_prefix="/investigacion",
)

F = TypeVar("F", bound=Callable[..., Any])

DATASET_LABELS: dict[str, str] = {
    "results": "Resultados RIASEC",
    "ml": "Machine Learning",
    "transformer": "NLP / Transformers",
    "master": "Maestro de auditoría",
    "quality": "Calidad de datos",
}


def _configured_accounts() -> list[dict[str, str]]:
    """Devuelve únicamente cuentas que poseen usuario y hash configurados."""

    accounts = current_app.config.get("RESEARCHER_ACCOUNTS", [])
    return [
        {
            "username": str(account.get("username", "")).strip().lower(),
            "display_name": str(account.get("display_name", "")).strip(),
            "password_hash": str(account.get("password_hash", "")).strip(),
            "role": str(account.get("role", "viewer")).strip().lower(),
        }
        for account in accounts
        if str(account.get("username", "")).strip()
        and str(account.get("password_hash", "")).strip()
    ]


def _csrf_token() -> str:
    """Obtiene o crea un token CSRF de sesión sin dependencias adicionales."""

    token = session.get("research_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["research_csrf_token"] = token
    return token


def _validate_csrf() -> None:
    """Rechaza formularios POST que no pertenezcan a la sesión actual."""

    expected = session.get("research_csrf_token", "")
    received = request.form.get("csrf_token", "")
    if not expected or not received or not hmac.compare_digest(expected, received):
        abort(400, description="Token de seguridad inválido o vencido.")


def researcher_required(view: F) -> F:
    """Protege vistas del módulo de investigación."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not session.get("researcher_username"):
            return redirect(url_for("research.login"))
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def data_manager_required(view: F) -> F:
    """Restringe operaciones sensibles al rol de gestión de datos."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not session.get("researcher_username"):
            return redirect(url_for("research.login"))
        if session.get("researcher_role") != "data_manager":
            abort(403, description="Esta operación requiere rol data_manager.")
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def _audit_research_event(
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: str | None = None,
) -> None:
    """Persiste una bitácora de acciones sensibles antes de responder."""

    event = ResearchAuditEvent(
        actor_username=str(session.get("researcher_username", "")),
        actor_role=str(session.get("researcher_role", "viewer")),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.session.add(event)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No fue posible registrar auditoría investigadora.")
        raise


def _researcher_context() -> dict[str, str]:
    return {
        "username": str(session.get("researcher_username", "")),
        "display_name": str(session.get("researcher_display_name", "Investigador")),
        "role": str(session.get("researcher_role", "viewer")),
    }


@research_bp.after_request
def private_cache_headers(response):
    """Evita que páginas/datasets privados queden cacheados por el navegador."""

    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@research_bp.route("/login", methods=["GET", "POST"])
def login():
    """Autentica a un investigador configurado en variables de entorno."""

    if session.get("researcher_username"):
        return redirect(url_for("research.dashboard"))

    accounts = _configured_accounts()
    configuration_ready = bool(accounts)
    error: str | None = None

    if request.method == "POST":
        _validate_csrf()
        if not configuration_ready:
            error = (
                "El acceso investigador todavía no tiene credenciales "
                "configuradas en el servidor."
            )
        else:
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            account = next(
                (
                    item
                    for item in accounts
                    if hmac.compare_digest(item["username"], username)
                ),
                None,
            )

            authenticated = bool(
                account
                and password
                and check_password_hash(account["password_hash"], password)
            )
            if authenticated and account is not None:
                session.clear()
                session["researcher_username"] = account["username"]
                session["researcher_display_name"] = (
                    account["display_name"] or account["username"]
                )
                session["researcher_role"] = (
                    account["role"]
                    if account["role"] in {"viewer", "data_manager"}
                    else "viewer"
                )
                _csrf_token()
                _audit_research_event(
                    action="login",
                    resource_type="research_module",
                )
                flash("Acceso investigador iniciado correctamente.", "success")
                return redirect(url_for("research.dashboard"))

            current_app.logger.warning(
                "Intento de acceso investigador fallido para usuario '%s'.",
                username or "<vacío>",
            )
            error = "Usuario o contraseña incorrectos."

    return render_template(
        "research_login.html",
        error=error,
        configuration_ready=configuration_ready,
        csrf_token=_csrf_token(),
    )


@research_bp.post("/logout")
@researcher_required
def logout():
    """Cierra la sesión privada del investigador."""

    _validate_csrf()
    _audit_research_event(
        action="logout",
        resource_type="research_module",
    )
    session.clear()
    flash("Sesión de investigación cerrada.", "success")
    return redirect(url_for("research.login"))


@research_bp.get("")
@research_bp.get("/")
@researcher_required
def dashboard():
    """Muestra indicadores, filtros, calidad y accesos de exportación."""

    try:
        filters = normalize_research_filters(request.args)
        summary = get_research_summary(filters)
        sessions = get_research_sessions(filters, limit=100)
        options = get_research_filter_options()
    except DatasetServiceError as exc:
        flash(str(exc), "error")
        filters = normalize_research_filters({})
        summary = get_research_summary(filters)
        sessions = get_research_sessions(filters, limit=100)
        options = get_research_filter_options()

    export_params = {
        key: value
        for key, value in filters.items()
        if value not in (None, "")
    }
    for key in ("started_from", "started_to"):
        if export_params.get(key) is not None:
            export_params[key] = export_params[key].isoformat()

    return render_template(
        "research_dashboard.html",
        researcher=_researcher_context(),
        csrf_token=_csrf_token(),
        filters=filters,
        summary=summary,
        sessions=sessions,
        options=options,
        dataset_labels=DATASET_LABELS,
        dataset_kinds=RESEARCH_DATASET_KINDS,
        export_query=urlencode(export_params),
    )


@research_bp.get("/datasets/export/<kind>/<file_format>")
@researcher_required
def export_dataset(kind: str, file_format: str):
    """Exporta el dataset filtrado en CSV o XLSX."""

    normalized_kind = kind.strip().lower()
    normalized_format = file_format.strip().lower()
    if normalized_kind not in RESEARCH_DATASET_KINDS:
        abort(404)
    if normalized_format not in {"csv", "xlsx"}:
        abort(404)
    if (
        normalized_kind in {"master", "quality"}
        and session.get("researcher_role") != "data_manager"
    ):
        abort(403, description="Este dataset requiere rol data_manager.")

    try:
        filters = normalize_research_filters(request.args)
        records = build_research_dataset(normalized_kind, filters)
    except DatasetServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("research.dashboard"))

    _audit_research_event(
        action="dataset_export",
        resource_type="dataset",
        resource_id=normalized_kind,
        details=f"format={normalized_format}; rows={len(records)}",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"riasec_{normalized_kind}_{timestamp}.{normalized_format}"

    if normalized_format == "csv":
        content = export_records_to_csv(records).encode("utf-8-sig")
        response = Response(content, mimetype="text/csv; charset=utf-8")
        response.headers[
            "Content-Disposition"
        ] = f'attachment; filename="{filename}"'
        return response

    payload = export_records_to_xlsx(
        records,
        sheet_title=DATASET_LABELS[normalized_kind],
    )
    return send_file(
        BytesIO(payload),
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name=filename,
    )


@research_bp.post("/calidad/<uuid:session_id>")
@data_manager_required
def update_quality(session_id: uuid.UUID):
    """Permite al investigador validar/excluir una sesión para datasets ML."""

    _validate_csrf()
    try:
        assessment = get_assessment(session_id)
        review = review_session_quality(
            assessment,
            quality_status=request.form.get("quality_status", "pending"),
            included_ml=request.form.get("included_ml") == "1",
            exclusion_reason=request.form.get("exclusion_reason") or None,
            dataset_version=request.form.get("dataset_version") or None,
            commit=False,
        )
        _audit_research_event(
            action="quality_review_update",
            resource_type="assessment",
            resource_id=str(session_id),
            details=(
                f"status={review.quality_status}; "
                f"included_ml={review.included_ml}; "
                f"dataset_version={review.dataset_version or ''}"
            ),
        )
    except AssessmentNotFoundError:
        abort(404)
    except DatasetServiceError as exc:
        flash(str(exc), "error")
    else:
        flash("Control de calidad actualizado.", "success")

    return redirect(url_for("research.dashboard"))
