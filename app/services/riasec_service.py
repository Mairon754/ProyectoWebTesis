"""Lógica de puntuación RIASEC/Holland.

FASE 3 — Servicios
------------------
Este módulo es la fuente de verdad para calcular los seis puntajes RIASEC,
ordenarlos y construir el código Holland. No contiene rutas HTTP ni lógica de
presentación.

Regla metodológica de este proyecto
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Las 60 respuestas oficiales O*NET producen la variable objetivo (Y). Por ello
este servicio calcula el resultado desde `ONetResponse` y nunca utiliza las
variables complementarias G01-G12, materias, actividades o textos abiertos.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models import AssessmentSession, RiasecResult

RIASEC_CODES: tuple[str, ...] = ("R", "I", "A", "S", "E", "C")
EXPECTED_TOTAL_ITEMS = 60
EXPECTED_ITEMS_PER_DIMENSION = 10
MIN_RAW_RESPONSE = 1
MAX_RAW_RESPONSE = 5
MIN_DIMENSION_SCORE = 0
MAX_DIMENSION_SCORE = 40
SCORING_VERSION = "RIASEC_SCORING_V1"

RIASEC_DIMENSION_INFO: dict[str, dict[str, Any]] = {
    "R": {
        "name": "Realista",
        "tagline": "Práctico, técnico y orientado a la acción",
        "description": (
            "Interés por actividades concretas, técnicas, manuales y por "
            "trabajar con objetos, herramientas, equipos o entornos físicos."
        ),
        "strengths": (
            "Orientación práctica y preferencia por resultados concretos",
            "Interés por construir, reparar, operar o trabajar con equipos",
            "Comodidad con actividades físicas, técnicas o al aire libre",
        ),
        "interests": (
            "tecnología aplicada y mantenimiento",
            "construcción, producción y trabajo manual",
            "actividades físicas y entornos naturales",
        ),
    },
    "I": {
        "name": "Investigador",
        "tagline": "Analítico, curioso y orientado a comprender",
        "description": (
            "Interés por investigar, analizar información, formular preguntas "
            "y resolver problemas mediante observación y razonamiento."
        ),
        "strengths": (
            "Curiosidad por explicar cómo y por qué ocurren las cosas",
            "Preferencia por analizar problemas antes de tomar decisiones",
            "Interés por experimentar, investigar y trabajar con evidencia",
        ),
        "interests": (
            "ciencia, investigación y laboratorio",
            "análisis de datos y resolución de problemas",
            "tecnología, salud y fenómenos naturales",
        ),
    },
    "A": {
        "name": "Artístico",
        "tagline": "Creativo, expresivo y abierto a nuevas ideas",
        "description": (
            "Interés por crear, comunicar y expresar ideas mediante recursos "
            "visuales, escritos, musicales, escénicos o audiovisuales."
        ),
        "strengths": (
            "Preferencia por crear y explorar soluciones originales",
            "Interés por comunicar ideas de manera expresiva",
            "Afinidad con tareas flexibles que permiten imaginación",
        ),
        "interests": (
            "diseño, escritura y creación visual",
            "música, artes escénicas y producción audiovisual",
            "comunicación y creación de contenido",
        ),
    },
    "S": {
        "name": "Social",
        "tagline": "Colaborativo y orientado a apoyar a otras personas",
        "description": (
            "Interés por enseñar, orientar, acompañar, cuidar y trabajar "
            "directamente con personas o comunidades."
        ),
        "strengths": (
            "Interés por explicar, acompañar y facilitar el aprendizaje",
            "Preferencia por actividades de ayuda y cooperación",
            "Afinidad con el trabajo interpersonal y comunitario",
        ),
        "interests": (
            "educación, orientación y acompañamiento",
            "salud, bienestar y servicio a personas",
            "trabajo comunitario y voluntariado",
        ),
    },
    "E": {
        "name": "Emprendedor",
        "tagline": "Iniciativa, liderazgo e influencia",
        "description": (
            "Interés por liderar, persuadir, negociar, organizar iniciativas y "
            "movilizar personas o recursos para alcanzar objetivos."
        ),
        "strengths": (
            "Preferencia por asumir iniciativa y coordinar actividades",
            "Interés por comunicar, negociar y defender propuestas",
            "Afinidad con metas, emprendimientos y toma de decisiones",
        ),
        "interests": (
            "emprendimiento, ventas y gestión",
            "liderazgo, negociación y organización",
            "proyectos, negocios e iniciativas propias",
        ),
    },
    "C": {
        "name": "Convencional",
        "tagline": "Organizado, sistemático y atento a los detalles",
        "description": (
            "Interés por organizar información, seguir procedimientos, "
            "mantener registros y trabajar con datos de forma estructurada."
        ),
        "strengths": (
            "Preferencia por el orden, la planificación y la precisión",
            "Interés por trabajar con registros, datos y procedimientos",
            "Afinidad con tareas estructuradas y seguimiento de detalles",
        ),
        "interests": (
            "organización de información y documentación",
            "administración, registros y control de procesos",
            "datos, herramientas digitales y planificación",
        ),
    },
}


class RiasecScoringError(ValueError):
    """Error de dominio al validar o calcular un resultado RIASEC."""


@dataclass(frozen=True, slots=True)
class RankedDimension:
    """Representa una dimensión y su puntaje dentro del ranking."""

    code: str
    score: int


def _normalized_area(value: Any) -> str:
    """Normaliza y valida un código de dimensión RIASEC."""

    area = str(value or "").strip().upper()
    if area not in RIASEC_CODES:
        raise RiasecScoringError(
            f"Dimensión RIASEC inválida: {value!r}."
        )
    return area


def _raw_value(response: Any) -> int:
    """Obtiene y valida la respuesta oficial 1-5 de un objeto respuesta."""

    raw = getattr(response, "response_raw", None)
    if isinstance(response, Mapping):
        raw = response.get("response_raw", raw)

    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RiasecScoringError(
            "Cada respuesta O*NET debe contener `response_raw` entero."
        )
    if not MIN_RAW_RESPONSE <= raw <= MAX_RAW_RESPONSE:
        raise RiasecScoringError(
            f"Respuesta O*NET fuera de rango: {raw}. Debe estar entre 1 y 5."
        )
    return raw


def _item_area(response: Any) -> str:
    """Obtiene la dimensión RIASEC del ítem relacionado con una respuesta."""

    if isinstance(response, Mapping):
        direct = response.get("area")
        if direct is not None:
            return _normalized_area(direct)
        item = response.get("item")
    else:
        item = getattr(response, "item", None)

    if item is None:
        raise RiasecScoringError(
            "La respuesta O*NET no tiene asociado su ítem."
        )

    area = getattr(item, "area", None)
    if isinstance(item, Mapping):
        area = item.get("area", area)

    return _normalized_area(area)


def _item_identity(response: Any) -> str:
    """Obtiene una identidad estable del ítem para detectar duplicados."""

    if isinstance(response, Mapping):
        item_id = response.get("item_id")
        item = response.get("item")
    else:
        item_id = getattr(response, "item_id", None)
        item = getattr(response, "item", None)

    if item_id is not None:
        return str(item_id)

    if item is not None:
        item_index = getattr(item, "item_index", None)
        if isinstance(item, Mapping):
            item_index = item.get("item_index", item_index)
        if item_index is not None:
            return f"index:{item_index}"

    raise RiasecScoringError(
        "No fue posible identificar el ítem de una respuesta O*NET."
    )


def validate_responses(
    responses: Iterable[Any],
    *,
    require_complete: bool = True,
) -> list[Any]:
    """Valida integridad, rango y distribución de respuestas O*NET.

    Args:
        responses: Respuestas con `response_raw` y relación `item.area`.
        require_complete: Cuando es True exige exactamente 60 respuestas y 10
            ítems por cada una de las seis dimensiones.

    Returns:
        Lista materializada de respuestas ya validadas.

    Raises:
        RiasecScoringError: Si existen respuestas inválidas o duplicadas.
    """

    materialized = list(responses)
    identities: set[str] = set()
    area_counts: Counter[str] = Counter()

    for response in materialized:
        identity = _item_identity(response)
        if identity in identities:
            raise RiasecScoringError(
                f"Se detectó una respuesta duplicada para el ítem {identity}."
            )
        identities.add(identity)

        _raw_value(response)
        area_counts[_item_area(response)] += 1

    if require_complete:
        if len(materialized) != EXPECTED_TOTAL_ITEMS:
            raise RiasecScoringError(
                "La evaluación O*NET debe contener exactamente "
                f"{EXPECTED_TOTAL_ITEMS} respuestas; se recibieron "
                f"{len(materialized)}."
            )

        invalid_distribution = {
            code: area_counts.get(code, 0)
            for code in RIASEC_CODES
            if area_counts.get(code, 0) != EXPECTED_ITEMS_PER_DIMENSION
        }
        if invalid_distribution:
            detail = ", ".join(
                f"{code}={count}"
                for code, count in invalid_distribution.items()
            )
            raise RiasecScoringError(
                "La distribución de ítems por dimensión no es válida. "
                f"Esperado: 10 por dimensión. Encontrado: {detail}."
            )

    return materialized


def calculate_scores(responses: Iterable[Any]) -> dict[str, int]:
    """Calcula los seis puntajes RIASEC en escala 0-40.

    La API del instrumento almacena 1-5. Para el cálculo local cada respuesta
    se transforma a 0-4 mediante `response_raw - 1`. Cada dimensión contiene
    diez ítems, por lo que cada puntaje final queda entre 0 y 40.
    """

    validated = validate_responses(responses, require_complete=True)
    scores: dict[str, int] = {code: 0 for code in RIASEC_CODES}

    for response in validated:
        area = _item_area(response)
        scores[area] += _raw_value(response) - 1

    validate_scores(scores)
    return scores


def validate_scores(scores: Mapping[str, int]) -> None:
    """Comprueba que un vector de puntajes RIASEC sea válido."""

    missing = [code for code in RIASEC_CODES if code not in scores]
    extras = [code for code in scores if code not in RIASEC_CODES]

    if missing or extras:
        raise RiasecScoringError(
            "Vector RIASEC inválido. "
            f"Faltantes={missing or 'ninguno'}, extras={extras or 'ninguno'}."
        )

    for code in RIASEC_CODES:
        score = scores[code]
        if isinstance(score, bool) or not isinstance(score, int):
            raise RiasecScoringError(
                f"El puntaje {code} debe ser entero; recibido {score!r}."
            )
        if not MIN_DIMENSION_SCORE <= score <= MAX_DIMENSION_SCORE:
            raise RiasecScoringError(
                f"El puntaje {code}={score} está fuera del rango 0-40."
            )


def rank_scores(scores: Mapping[str, int]) -> list[RankedDimension]:
    """Ordena dimensiones por puntaje sin ocultar empates.

    El orden R-I-A-S-E-C se utiliza únicamente como orden estable de salida
    cuando dos dimensiones tienen el mismo puntaje. Nunca se utiliza ese orden
    para resolver un empate psicométrico ni para asignar un perfil ganador.
    """

    validate_scores(scores)
    position = {code: index for index, code in enumerate(RIASEC_CODES)}

    return sorted(
        (RankedDimension(code=code, score=scores[code]) for code in RIASEC_CODES),
        key=lambda entry: (-entry.score, position[entry.code]),
    )


def _ranking_groups(
    ranking: Iterable[RankedDimension],
) -> list[list[RankedDimension]]:
    """Agrupa dimensiones que poseen exactamente el mismo puntaje."""

    groups: list[list[RankedDimension]] = []
    by_score: dict[int, list[RankedDimension]] = defaultdict(list)

    for entry in ranking:
        by_score[entry.score].append(entry)

    for score in sorted(by_score, reverse=True):
        groups.append(by_score[score])

    return groups


def determine_profiles(scores: Mapping[str, int]) -> dict[str, Any]:
    """Obtiene perfiles y código Holland preservando empates.

    Política de empates:
    - Si el primer puesto está empatado, no se inventa `profile_1` ni código.
    - Si el primer puesto es único pero existe un empate que cruza las
      posiciones 2 o 3, se conserva el perfil 1, pero el código Holland queda
      nulo porque el orden de las letras siguientes no es inequívoco.
    - Solo se construye un código de tres letras cuando los tres primeros
      puestos son unívocos.
    """

    ranking = rank_scores(scores)
    groups = _ranking_groups(ranking)
    top_group = groups[0]
    top_candidates = [entry.code for entry in top_group]
    tie_top1 = len(top_group) > 1

    result: dict[str, Any] = {
        "profile_1": None,
        "profile_2": None,
        "profile_3": None,
        "holland_code": None,
        "tie_top1": tie_top1,
        "top1_candidates": top_candidates if tie_top1 else None,
        "ranking": [
            {"code": entry.code, "score": entry.score}
            for entry in ranking
        ],
    }

    if tie_top1:
        return result

    result["profile_1"] = top_group[0].code

    # Para obtener tres posiciones inequívocas necesitamos tres grupos de un
    # solo elemento. Un empate en posición 2/3 impide construir Holland code.
    if len(groups) < 2 or len(groups[1]) != 1:
        return result

    result["profile_2"] = groups[1][0].code

    if len(groups) < 3 or len(groups[2]) != 1:
        return result

    result["profile_3"] = groups[2][0].code
    result["holland_code"] = (
        result["profile_1"]
        + result["profile_2"]
        + result["profile_3"]
    )
    return result


def build_result_payload(responses: Iterable[Any]) -> dict[str, Any]:
    """Calcula y serializa el resultado completo sin persistirlo."""

    scores = calculate_scores(responses)
    profiles = determine_profiles(scores)

    return {
        "scores": dict(scores),
        **profiles,
        "scoring_version": SCORING_VERSION,
    }


def calculate_session_result(
    assessment_session: AssessmentSession,
    *,
    commit: bool = True,
) -> RiasecResult:
    """Calcula y persiste el resultado oficial de una sesión.

    Si la sesión ya tiene `RiasecResult`, se actualiza en lugar de crear un
    duplicado. Esta operación es idempotente respecto a la misma colección de
    respuestas.
    """

    if assessment_session is None:
        raise RiasecScoringError("La sesión de evaluación es obligatoria.")

    payload = build_result_payload(assessment_session.onet_responses)
    scores = payload["scores"]

    result = assessment_session.riasec_result
    if result is None:
        result = RiasecResult(session_id=assessment_session.id)
        db.session.add(result)

    result.score_r = scores["R"]
    result.score_i = scores["I"]
    result.score_a = scores["A"]
    result.score_s = scores["S"]
    result.score_e = scores["E"]
    result.score_c = scores["C"]
    result.profile_1 = payload["profile_1"]
    result.profile_2 = payload["profile_2"]
    result.profile_3 = payload["profile_3"]
    result.holland_code = payload["holland_code"]
    result.tie_top1 = payload["tie_top1"]
    result.top1_candidates = payload["top1_candidates"]
    result.scoring_version = SCORING_VERSION
    result.calculated_at = datetime.now(timezone.utc)

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    return result

def persisted_scores(result: RiasecResult) -> dict[str, int]:
    """Extrae y valida los seis puntajes ya persistidos en PostgreSQL."""

    if result is None:
        raise RiasecScoringError("El resultado RIASEC es obligatorio.")

    scores = {
        "R": result.score_r,
        "I": result.score_i,
        "A": result.score_a,
        "S": result.score_s,
        "E": result.score_e,
        "C": result.score_c,
    }
    validate_scores(scores)
    return scores


def build_result_interpretation(result: RiasecResult) -> dict[str, Any]:
    """Construye la interpretación textual oficial para frontend y API.

    Esta función no recalcula las respuestas O*NET. Trabaja únicamente con
    los puntajes oficiales ya persistidos y genera información de presentación
    e interpretación. Así el frontend no contiene reglas psicológicas ni de
    ordenamiento del perfil.
    """

    scores = persisted_scores(result)
    ranking = rank_scores(scores)

    # El corte incluye cualquier empate que cruce la tercera posición. De ese
    # modo nunca ocultamos una dimensión con el mismo puntaje que otra mostrada
    # como principal.
    cutoff_score = ranking[min(2, len(ranking) - 1)].score
    primary_codes = [
        entry.code for entry in ranking if entry.score >= cutoff_score
    ]

    unique_scores = sorted(set(scores.values()), reverse=True)
    rank_by_score = {
        score: index + 1 for index, score in enumerate(unique_scores)
    }

    dimensions: list[dict[str, Any]] = []
    for code in RIASEC_CODES:
        info = RIASEC_DIMENSION_INFO[code]
        score = scores[code]
        dimensions.append(
            {
                "code": code,
                "name": info["name"],
                "tagline": info["tagline"],
                "score": score,
                "percentage": round((score / MAX_DIMENSION_SCORE) * 100),
                "rank": rank_by_score[score],
                "is_primary": code in primary_codes,
                "description": info["description"],
                "strengths": list(info["strengths"]),
                "interests": list(info["interests"]),
            }
        )

    by_code = {item["code"]: item for item in dimensions}
    ranking_data = [by_code[entry.code] for entry in ranking]
    primary_dimensions = [by_code[code] for code in primary_codes]

    if result.tie_top1:
        top_candidates = list(result.top1_candidates or [])
        if not top_candidates:
            highest = ranking[0].score
            top_candidates = [
                entry.code for entry in ranking if entry.score == highest
            ]
        names = [RIASEC_DIMENSION_INFO[code]["name"] for code in top_candidates]
        profile_summary = (
            "Tu puntuación más alta está compartida por "
            + ", ".join(names)
            + ". El perfil se interpreta como una combinación de intereses "
            "sin forzar una única dimensión principal."
        )
        code_explanation = (
            "No se genera un código RIASEC de tres letras porque existe un "
            "empate en la primera posición. Conservar el empate evita producir "
            "una clasificación arbitraria."
        )
    elif result.holland_code:
        code_names = [
            RIASEC_DIMENSION_INFO[code]["name"]
            for code in result.holland_code
        ]
        profile_summary = (
            f"Tu patrón principal es {result.holland_code}: "
            + ", ".join(code_names)
            + ". Estas son las tres áreas que alcanzaron las puntuaciones "
            "más altas en esta evaluación, en ese orden."
        )
        code_explanation = (
            "El código RIASEC resume las tres dimensiones con mayor puntaje. "
            "La primera letra representa la puntuación principal y las dos "
            "siguientes complementan el patrón de intereses."
        )
    else:
        primary_name = (
            RIASEC_DIMENSION_INFO[result.profile_1]["name"]
            if result.profile_1
            else "una combinación de áreas"
        )
        profile_summary = (
            f"Tu área principal es {primary_name}. Existe un empate en "
            "posiciones posteriores, por lo que no se construye un código "
            "RIASEC de tres letras de manera artificial."
        )
        code_explanation = (
            "El sistema conserva los empates tal como aparecen en los "
            "puntajes. Por eso puede existir una dimensión principal sin un "
            "código completo de tres letras."
        )

    return {
        "dimensions": dimensions,
        "ranking": ranking_data,
        "primary_dimensions": primary_dimensions,
        "primary_codes": primary_codes,
        "profile_summary": profile_summary,
        "code_explanation": code_explanation,
        "disclaimer": (
            "Este resultado describe intereses reportados durante la prueba. "
            "No mide por sí solo aptitudes, rendimiento académico ni determina "
            "qué carrera debes elegir; se utiliza como apoyo para explorar "
            "opciones formativas y ocupacionales."
        ),
    }


def serialize_persisted_result(
    assessment_session: AssessmentSession,
) -> dict[str, Any]:
    """Serializa resultado e interpretación oficial para la API REST."""

    if assessment_session is None:
        raise RiasecScoringError("La sesión de evaluación es obligatoria.")
    result = assessment_session.riasec_result
    if result is None:
        raise RiasecScoringError(
            "La evaluación todavía no tiene resultado RIASEC."
        )

    interpretation = build_result_interpretation(result)
    return {
        "session_id": str(assessment_session.id),
        "scores": persisted_scores(result),
        "profile_1": result.profile_1,
        "profile_2": result.profile_2,
        "profile_3": result.profile_3,
        "holland_code": result.holland_code,
        "tie_top1": result.tie_top1,
        "top1_candidates": list(result.top1_candidates or []),
        "scoring_version": result.scoring_version,
        "calculated_at": (
            result.calculated_at.isoformat()
            if result.calculated_at is not None
            else None
        ),
        "interpretation": interpretation,
    }

