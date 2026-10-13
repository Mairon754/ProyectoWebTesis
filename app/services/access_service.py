"""Control de acceso a evaluaciones anónimas.

FASE 4 — Integridad, privacidad y acceso
----------------------------------------
Una UUID de sesión no constituye autorización. El flujo web queda ligado a la
sesión Flask firmada del navegador y los clientes API pueden usar un token
HMAC separado enviado exclusivamente en cabecera.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

from flask import current_app, request, session


ASSESSMENT_ACCESS_HEADER = "X-Assessment-Token"
ASSESSMENT_ACCESS_TOKEN_VERSION = "aat1"


class AssessmentAccessError(PermissionError):
    """La solicitud no demuestra posesión de la evaluación."""


def _canonical_session_id(session_id: uuid.UUID | str) -> str:
    try:
        return str(uuid.UUID(str(session_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssessmentAccessError("Identificador de evaluación inválido.") from exc


def issue_assessment_access_token(session_id: uuid.UUID | str) -> str:
    """Emite un token de capacidad determinista ligado al SECRET_KEY actual."""

    canonical = _canonical_session_id(session_id)
    secret = str(current_app.config.get("SECRET_KEY", "")).encode("utf-8")
    if not secret:
        raise RuntimeError("SECRET_KEY es obligatoria para tokens de evaluación.")
    message = f"{ASSESSMENT_ACCESS_TOKEN_VERSION}:{canonical}".encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{ASSESSMENT_ACCESS_TOKEN_VERSION}.{digest}"


def verify_assessment_access_token(
    session_id: uuid.UUID | str,
    token: Any,
) -> bool:
    """Valida en tiempo constante el token API de una evaluación."""

    if not isinstance(token, str) or not token.strip():
        return False
    try:
        expected = issue_assessment_access_token(session_id)
    except AssessmentAccessError:
        return False
    return hmac.compare_digest(expected, token.strip())


def bind_assessment_to_browser(session_id: uuid.UUID | str) -> None:
    """Vincula la evaluación a la cookie Flask firmada del navegador actual."""

    session["active_assessment_id"] = _canonical_session_id(session_id)


def browser_owns_assessment(session_id: uuid.UUID | str) -> bool:
    """Comprueba que la evaluación pertenece al flujo web del navegador."""

    active = str(session.get("active_assessment_id", "")).strip()
    if not active:
        return False
    try:
        canonical = _canonical_session_id(session_id)
    except AssessmentAccessError:
        return False
    return hmac.compare_digest(active, canonical)


def request_has_assessment_access(session_id: uuid.UUID | str) -> bool:
    """Acepta propiedad de navegador o token de capacidad en cabecera."""

    if browser_owns_assessment(session_id):
        return True
    token = request.headers.get(ASSESSMENT_ACCESS_HEADER, "")
    return verify_assessment_access_token(session_id, token)


def require_assessment_access(session_id: uuid.UUID | str) -> None:
    """Rechaza acceso por UUID sin prueba de posesión."""

    if not request_has_assessment_access(session_id):
        raise AssessmentAccessError(
            "No estás autorizado para acceder o modificar esta evaluación."
        )
