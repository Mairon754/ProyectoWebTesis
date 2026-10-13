"""Protocolo reproducible para instrumento, puntuación y objetivos RIASEC.

FASE 3 — Verdad científica
--------------------------
Este módulo separa tres conceptos que no deben confundirse:

1. contenido local congelado del instrumento;
2. regla computacional de puntuación;
3. definición de las variables objetivo Y.

La propuesta suministrada no identifica con suficiente precisión la versión
exacta, manual de puntuación ni evidencia documental de la adaptación usada.
Por ello, la implementación permanece científicamente "unverified" hasta que
esa evidencia sea incorporada y revisada.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any


RIASEC_CODES: tuple[str, ...] = ("R", "I", "A", "S", "E", "C")

INSTRUMENT_VERIFICATION_UNVERIFIED = "unverified"
INSTRUMENT_VERIFICATION_VERIFIED = "verified"
INSTRUMENT_VERIFICATION_REJECTED = "rejected"
INSTRUMENT_VERIFICATION_STATUSES = {
    INSTRUMENT_VERIFICATION_UNVERIFIED,
    INSTRUMENT_VERIFICATION_VERIFIED,
    INSTRUMENT_VERIFICATION_REJECTED,
}

# La regla computacional aún no se presenta como regla psicométrica validada
# por una fuente documental del corpus.
SCORING_VERSION = "RIASEC_SCORING_PROVISIONAL_V1"

# Los seis puntajes dimensionales son el objetivo primario. Los perfiles
# ordenados y el código Holland son salidas derivadas.
TARGET_PROTOCOL_VERSION = "RIASEC_TARGETS_V1_SIX_SCORES_PRIMARY"

PRIMARY_TARGET_COLUMNS: tuple[str, ...] = (
    "score_r",
    "score_i",
    "score_a",
    "score_s",
    "score_e",
    "score_c",
)

DERIVED_TARGET_COLUMNS: tuple[str, ...] = (
    "profile_1",
    "profile_2",
    "profile_3",
    "holland_code",
    "tie_top1",
)

SCORING_SPEC: dict[str, Any] = {
    "protocol": SCORING_VERSION,
    "raw_response_min": 1,
    "raw_response_max": 5,
    "transform": "response_raw_minus_1",
    "items_per_dimension": 10,
    "dimension_score_min": 0,
    "dimension_score_max": 40,
    "dimensions": list(RIASEC_CODES),
    "tie_policy": (
        "preserve_exact_ties; do_not_force_profile_1_on_top_tie; "
        "do_not_force_three_letter_code_when_top_three_are_not_unique"
    ),
}


def _sha256_json(value: Any) -> str:
    """Calcula SHA-256 sobre JSON canónico UTF-8."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


SCORING_SPEC_SHA256 = _sha256_json(SCORING_SPEC)


def instrument_manifest(
    items: Iterable[tuple[int, str, str]],
) -> list[dict[str, Any]]:
    """Construye un manifiesto canónico de los ítems locales congelados."""

    return [
        {
            "item_index": int(index),
            "item_code": f"IP{int(index):02d}",
            "area": str(area).strip().upper(),
            "question_text": str(question_text),
        }
        for index, area, question_text in items
    ]


def instrument_content_sha256(
    items: Iterable[tuple[int, str, str]],
) -> str:
    """Hash del contenido LOCAL congelado.

    Detecta cambios del manifiesto almacenado en el repositorio. No demuestra
    por sí mismo coincidencia con una fuente externa ni validez psicométrica.
    """

    return _sha256_json(instrument_manifest(items))
