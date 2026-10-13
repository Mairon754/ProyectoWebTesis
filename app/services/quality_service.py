"""Control automático reproducible de calidad de datos.

FASE 6 — Control de calidad automático
---------------------------------------
El protocolo aplica únicamente reglas deterministas respaldadas por el flujo
del instrumento y la propuesta: completitud, consistencia estructural, rangos
válidos, presencia de resultados y coherencia de metadatos. No inventa
umbrales psicométricos, tiempos mínimos ni criterios de exclusión estadística.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models import AssessmentSession, AutomaticQualityCheck


AUTOMATIC_QUALITY_PROTOCOL_VERSION = "DATA_QC_V1_STRUCTURAL_COMPLETENESS"


class AutomaticQualityError(ValueError):
    """Error de dominio durante el control automático."""


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


def _snapshot(session: AssessmentSession) -> dict[str, Any]:
    """Construye la entrada determinista utilizada por el protocolo QC."""

    onet = sorted(
        [
            {
                "item_code": response.item.item_code,
                "response_raw": response.response_raw,
                "response_score": response.response_score,
                "response_time_ms": response.response_time_ms,
            }
            for response in session.onet_responses
        ],
        key=lambda row: row["item_code"],
    )
    interests = sorted(
        [
            {
                "code": response.item.code,
                "value": response.response_value,
            }
            for response in session.interest_responses
        ],
        key=lambda row: row["code"],
    )
    texts = sorted(
        [
            {
                "prompt_code": response.prompt_code,
                "text": response.response_text,
                "word_count": response.word_count,
            }
            for response in session.open_responses
        ],
        key=lambda row: row["prompt_code"],
    )
    result = session.riasec_result
    return {
        "session_id": str(session.id),
        "status": session.status,
        "collection_phase": session.collection_phase,
        "grade": session.grade,
        "municipality": session.municipality,
        "institution_code": session.institution_code,
        "instrument_version": session.instrument_version.code,
        "instrument_verification_status": (
            session.instrument_version.verification_status
        ),
        "instrument_hash": (
            session.instrument_version.local_content_hash_sha256
        ),
        "scoring_hash": session.instrument_version.scoring_spec_sha256,
        "onet": onet,
        "interests": interests,
        "subjects": sorted(link.subject.code for link in session.subject_links),
        "activities": sorted(
            link.activity.code for link in session.activity_links
        ),
        "texts": texts,
        "result": None
        if result is None
        else {
            "score_r": result.score_r,
            "score_i": result.score_i,
            "score_a": result.score_a,
            "score_s": result.score_s,
            "score_e": result.score_e,
            "score_c": result.score_c,
            "scoring_version": result.scoring_version,
        },
    }


def evaluate_automatic_quality(session: AssessmentSession) -> dict[str, Any]:
    """Evalúa una sesión sin modificar decisiones humanas de inclusión."""

    if session is None:
        raise AutomaticQualityError("La sesión es obligatoria.")

    checks: list[dict[str, Any]] = []

    def add(
        code: str,
        passed: bool,
        *,
        severity: str,
        message: str,
        observed: Any = None,
        expected: Any = None,
    ) -> None:
        checks.append(
            {
                "code": code,
                "passed": bool(passed),
                "severity": severity,
                "message": message,
                "observed": observed,
                "expected": expected,
            }
        )

    add(
        "session_completed",
        session.status == "completed",
        severity="blocker",
        message="La sesión debe estar finalizada.",
        observed=session.status,
        expected="completed",
    )

    onet_codes = [r.item.item_code for r in session.onet_responses]
    add(
        "onet_exactly_60",
        len(onet_codes) == 60 and len(set(onet_codes)) == 60,
        severity="blocker",
        message="Deben existir exactamente 60 respuestas O*NET únicas.",
        observed=len(onet_codes),
        expected=60,
    )
    add(
        "onet_values_in_range",
        all(1 <= r.response_raw <= 5 for r in session.onet_responses),
        severity="blocker",
        message="Todas las respuestas O*NET deben estar entre 1 y 5.",
    )
    add(
        "onet_scores_consistent",
        all(r.response_score == r.response_raw - 1 for r in session.onet_responses),
        severity="blocker",
        message="response_score debe corresponder a response_raw - 1.",
    )
    add(
        "response_times_nonnegative",
        all(
            r.response_time_ms is None or r.response_time_ms >= 0
            for r in session.onet_responses
        ),
        severity="blocker",
        message="Los tiempos registrados no pueden ser negativos.",
    )
    missing_times = sum(
        r.response_time_ms is None for r in session.onet_responses
    )
    add(
        "response_time_metadata_present",
        missing_times == 0,
        severity="warning",
        message=(
            "Se recomienda conservar tiempo de respuesta para todos los ítems; "
            "no se usa un umbral de velocidad para excluir estudiantes."
        ),
        observed=missing_times,
        expected=0,
    )

    interest_codes = [r.item.code for r in session.interest_responses]
    add(
        "interest_exactly_12",
        len(interest_codes) == 12 and len(set(interest_codes)) == 12,
        severity="blocker",
        message="Deben existir exactamente 12 respuestas complementarias únicas.",
        observed=len(interest_codes),
        expected=12,
    )
    add(
        "interest_values_in_range",
        all(1 <= r.response_value <= 5 for r in session.interest_responses),
        severity="blocker",
        message="Las respuestas G01-G12 deben estar entre 1 y 5.",
    )
    add(
        "subject_selection_present",
        len(session.subject_links) >= 1,
        severity="blocker",
        message="Debe existir al menos una materia seleccionada.",
        observed=len(session.subject_links),
        expected=">=1",
    )
    add(
        "activity_selection_present",
        len(session.activity_links) >= 1,
        severity="blocker",
        message="Debe existir al menos una actividad seleccionada.",
        observed=len(session.activity_links),
        expected=">=1",
    )

    text_by_code = {r.prompt_code: r for r in session.open_responses}
    for prompt in ("T01", "T02"):
        response = text_by_code.get(prompt)
        valid = bool(response and response.response_text.strip())
        add(
            f"{prompt.lower()}_required_text_present",
            valid,
            severity="blocker",
            message=f"{prompt} es una respuesta abierta obligatoria.",
        )
    t03 = text_by_code.get("T03")
    add(
        "t03_optional_text_present",
        bool(t03 and t03.response_text.strip()),
        severity="warning",
        message="T03 es opcional; su ausencia no excluye el registro.",
    )
    word_count_consistent = all(
        response.word_count == len(response.response_text.split())
        for response in session.open_responses
    )
    add(
        "open_text_word_counts_consistent",
        word_count_consistent,
        severity="blocker",
        message="El conteo almacenado debe coincidir con el texto original.",
    )

    result = session.riasec_result
    add(
        "riasec_result_present",
        result is not None,
        severity="blocker",
        message="La sesión debe poseer resultado RIASEC materializado.",
    )
    if result is not None:
        scores = [
            result.score_r, result.score_i, result.score_a,
            result.score_s, result.score_e, result.score_c,
        ]
        add(
            "riasec_scores_in_range",
            all(0 <= value <= 40 for value in scores),
            severity="blocker",
            message="Cada puntaje RIASEC debe estar en el rango 0-40.",
        )

    add(
        "scientific_hashes_present",
        bool(
            session.instrument_version.local_content_hash_sha256
            and session.instrument_version.scoring_spec_sha256
        ),
        severity="blocker",
        message="El instrumento y scoring deben conservar hashes científicos.",
    )

    if session.collection_phase == "final":
        add(
            "final_grade_11",
            session.grade == 11,
            severity="blocker",
            message="La muestra definitiva solo admite grado 11.",
            observed=session.grade,
            expected=11,
        )
        add(
            "final_instrument_verified",
            session.instrument_version.verification_status == "verified",
            severity="blocker",
            message=(
                "La recolección final requiere validación profesional/local "
                "documentada del instrumento."
            ),
            observed=session.instrument_version.verification_status,
            expected="verified",
        )

    blockers = [
        item for item in checks
        if item["severity"] == "blocker" and not item["passed"]
    ]
    warnings = [
        item for item in checks
        if item["severity"] == "warning" and not item["passed"]
    ]
    snapshot = _snapshot(session)
    return {
        "protocol_version": AUTOMATIC_QUALITY_PROTOCOL_VERSION,
        "input_hash_sha256": _sha256(snapshot),
        "status": "blocked" if blockers else "passed",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "checks": checks,
        "observations": {
            "blockers": [item["code"] for item in blockers],
            "warnings": [item["code"] for item in warnings],
            "note": (
                "No se aplican umbrales automáticos de velocidad, longitud "
                "mínima de texto, balance de clases ni detección psicométrica "
                "de respuestas atípicas porque el corpus adjunto no fija esos "
                "criterios."
            ),
        },
    }


def run_automatic_quality_check(
    session: AssessmentSession,
    *,
    commit: bool = True,
) -> AutomaticQualityCheck:
    """Evalúa y persiste una nueva ejecución histórica del protocolo."""

    result = evaluate_automatic_quality(session)
    check = AutomaticQualityCheck(
        session_id=session.id,
        protocol_version=result["protocol_version"],
        input_hash_sha256=result["input_hash_sha256"],
        status=result["status"],
        blocker_count=result["blocker_count"],
        warning_count=result["warning_count"],
        checks_json=result["checks"],
        observations_json=result["observations"],
    )
    db.session.add(check)
    try:
        if commit:
            db.session.commit()
        else:
            db.session.flush()
    except Exception:
        db.session.rollback()
        raise
    return check


def latest_automatic_quality_check(
    session_id,
) -> AutomaticQualityCheck | None:
    """Devuelve la ejecución más reciente del protocolo vigente."""

    return db.session.execute(
        select(AutomaticQualityCheck)
        .where(
            AutomaticQualityCheck.session_id == session_id,
            AutomaticQualityCheck.protocol_version
            == AUTOMATIC_QUALITY_PROTOCOL_VERSION,
        )
        .order_by(
            AutomaticQualityCheck.created_at.desc(),
            AutomaticQualityCheck.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def automatic_quality_is_current_and_passed(
    session: AssessmentSession,
) -> bool:
    """Exige resultado vigente, aprobado y correspondiente al estado actual."""

    latest = latest_automatic_quality_check(session.id)
    if latest is None or latest.status != "passed":
        return False
    current_hash = evaluate_automatic_quality(session)["input_hash_sha256"]
    return latest.input_hash_sha256 == current_hash
