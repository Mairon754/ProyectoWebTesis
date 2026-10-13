"""Protocolo reproducible para instrumento, puntuación y objetivos RIASEC.

FASE 3 — Verdad científica
--------------------------
Este módulo separa tres conceptos que no deben confundirse:

1. contenido local congelado del instrumento;
2. regla computacional de puntuación;
3. definición de las variables objetivo Y.

La fuente oficial externa fue contrastada el 2026-10-13 contra O*NET® Web
Services (Mi Próximo Paso) y el manual técnico del O*NET® Interest Profiler.
Los 60 ítems locales, su orden y asignación RIASEC coinciden con la forma corta
española publicada por el servicio. La validación global del producto sigue
separada de esta verificación de procedencia.
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

# Regla de puntuación confirmada contra el manual técnico oficial:
# entrada web 1-5, transformación equivalente a 0-4 y suma de 10 ítems por
# dimensión, con rango final 0-40.
SCORING_VERSION = "ONET_IP_SHORT_FORM_SCORING_V1"

SOURCE_QUESTION_LIST_REVISION = "2018-05-01"
SOURCE_VERIFICATION_DATE = "2026-10-13"
OFFICIAL_SOURCE_MANIFEST_SHA256 = (
    "c30279b792fde80681f96f1c3108ccbedbcb7547dbdee29a90c2d48221433c43"
)

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

    Detecta cambios del manifiesto almacenado en el repositorio. La igualdad
    con OFFICIAL_SOURCE_MANIFEST_SHA256 permite comprobar que el contenido
    local sigue siendo el mismo que fue contrastado con la fuente oficial.
    """

    return _sha256_json(instrument_manifest(items))
