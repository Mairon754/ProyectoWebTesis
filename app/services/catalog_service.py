"""Carga y consulta de catálogos maestros de la plataforma RIASEC.

FASE 3.1 — Corrección autorizada antes de Fase 4
------------------------------------------------
Los modelos y servicios de evaluación dependen de catálogos persistentes:
dimensiones RIASEC, instrumento/versiones, 60 ítems O*NET, G01-G12,
materias y actividades.

Este módulo concentra esa responsabilidad para evitar sembrar datos en rutas,
modelos o durante cada arranque de Flask. La carga es manual e idempotente
mediante el comando ``flask seed-catalogs`` registrado en ``create_app``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Activity,
    Instrument,
    InstrumentVersion,
    InterestItem,
    ONetItem,
    RiasecDimension,
    Subject,
)
from app.services.riasec_protocol import (
    INSTRUMENT_VERIFICATION_UNVERIFIED,
    OFFICIAL_SOURCE_MANIFEST_SHA256,
    SCORING_SPEC_SHA256,
    SOURCE_VERIFICATION_STATUS,
    instrument_content_sha256,
)

INSTRUMENT_CODE = "ONET_IP_SHORT_FORM"
INSTRUMENT_VERSION_CODE = "IP_ES_60_V1"

RIASEC_DIMENSIONS: tuple[tuple[str, str, str, int], ...] = (
    ("R", "Realistic", "Realista", 1),
    ("I", "Investigative", "Investigativo", 2),
    ("A", "Artistic", "Artístico", 3),
    ("S", "Social", "Social", 4),
    ("E", "Enterprising", "Emprendedor", 5),
    ("C", "Conventional", "Convencional", 6),
)

ONET_ITEMS: tuple[tuple[int, str, str], ...] = (
    (1, "R", "Construir gabinetes para cocinas"),
    (2, "R", "Colocar ladrillos o losetas"),
    (3, "I", "Elaborar nueva medicina"),
    (4, "I", "Estudiar maneras para reducir la contaminación del agua"),
    (5, "A", "Escribir libros u obras de teatro"),
    (6, "A", "Tocar un instrumento musical"),
    (7, "S", "Enseñar a una persona un ejercicio de rutina"),
    (8, "S", "Ayudar a personas con problemas personales o emocionales"),
    (9, "E", "Comprar y vender acciones y bonos"),
    (10, "E", "Administrar una tienda de venta al por menor o menudeo"),
    (11, "C", "Desarrollar una hoja de cálculo utilizando software"),
    (12, "C", "Revisar y corregir errores en registros o formularios"),
    (13, "R", "Reparar electrodomésticos"),
    (14, "R", "Criar peces en un criadero de peces"),
    (15, "I", "Realizar experimentos químicos"),
    (16, "I", "Estudiar los movimientos de los planetas"),
    (17, "A", "Componer y hacer arreglos musicales"),
    (18, "A", "Hacer dibujos"),
    (19, "S", "Orientar a las personas sobre carreras"),
    (20, "S", "Realizar terapia de rehabilitación"),
    (21, "E", "Administrar un salón de belleza o barbería"),
    (22, "E", "Administrar un departamento en una compañía grande"),
    (23, "C", "Instala software en las computadoras en una gran red"),
    (24, "C", "Operar una calculadora"),
    (25, "R", "Ensamblar partes electrónicas"),
    (26, "R", "Manejar un camión para entregar paquetes a oficinas y hogares"),
    (27, "I", "Examinar muestras de sangre con el uso de un microscopio"),
    (28, "I", "Investigar las causas de un incendio"),
    (29, "A", "Crear efectos especiales para películas"),
    (30, "A", "Pintar escenografías para obras de teatro"),
    (31, "S", "Hacer trabajo voluntario en organizaciones sin fines de lucro"),
    (32, "S", "Enseñar a niños cómo jugar deportes"),
    (33, "E", "Comenzar su propio negocio"),
    (34, "E", "Negociar contratos comerciales"),
    (35, "C", "Mantener registros de envíos y recepción"),
    (36, "C", "Calcular los salarios de los empleados"),
    (37, "R", "Probar la calidad de las partes antes de un envío"),
    (38, "R", "Reparar e instalar cerraduras"),
    (
        39,
        "I",
        "Desarrollar una mejor manera de predecir el estado del tiempo o clima",
    ),
    (40, "I", "Trabajar en un laboratorio de biología"),
    (41, "A", "Escribir libretos para películas o programas de televisión"),
    (42, "A", "Realizar un baile de jazz o tap"),
    (
        43,
        "S",
        "Enseñar lenguaje por señas a personas que son sordas o tienen "
        "problemas de audición",
    ),
    (44, "S", "Ayudar a realizar sesiones de terapia de grupo"),
    (45, "E", "Representar a un cliente en una demanda"),
    (46, "E", "Comercializar una nueva línea de ropa"),
    (
        47,
        "C",
        "Identificar el inventario de suministros con una computadora de mano",
    ),
    (48, "C", "Llevar registros de pagos de renta"),
    (49, "R", "Montar y operar máquinas para la elaboración de productos"),
    (50, "R", "Apagar fuegos forestales"),
    (51, "I", "Inventar un substituto de azúcar"),
    (52, "I", "Hacer pruebas de laboratorio para identificar enfermedades"),
    (53, "A", "Cantar en una banda o grupo"),
    (54, "A", "Editar películas"),
    (55, "S", "Cuidar niños en un centro de cuidado infantil"),
    (56, "S", "Enseñar una clase de high school"),
    (57, "E", "Vender mercancía en una tienda por departamentos"),
    (58, "E", "Administrar una tienda de ropa"),
    (59, "C", "Mantener registros de inventarios"),
    (60, "C", "Colocar sellos, separar y repartir correo para una organización"),
)

INTEREST_ITEMS: tuple[tuple[str, str, int], ...] = (
    ("G01", "Crear o editar videos, fotografías o contenido digital", 1),
    (
        "G02",
        "Aprender sobre programación, inteligencia artificial o nuevas tecnologías",
        2,
    ),
    (
        "G03",
        "Jugar videojuegos que impliquen estrategia, construcción o resolución "
        "de problemas",
        3,
    ),
    (
        "G04",
        "Reparar, armar o modificar objetos, dispositivos o equipos",
        4,
    ),
    ("G05", "Realizar actividades deportivas, físicas o al aire libre", 5),
    (
        "G06",
        "Investigar por qué ocurren las cosas y buscar explicaciones por tu cuenta",
        6,
    ),
    ("G07", "Explicar temas o ayudar a otras personas a aprender algo", 7),
    (
        "G08",
        "Participar en actividades comunitarias o ayudar a personas que lo necesitan",
        8,
    ),
    (
        "G09",
        "Organizar grupos, eventos o actividades y asumir el liderazgo",
        9,
    ),
    (
        "G10",
        "Vender, promocionar o desarrollar una idea, producto o emprendimiento",
        10,
    ),
    (
        "G11",
        "Dibujar, diseñar, escribir, hacer música o crear contenido original",
        11,
    ),
    (
        "G12",
        "Organizar información, planificar actividades o trabajar con datos y "
        "herramientas digitales",
        12,
    ),
)

SUBJECTS: tuple[tuple[str, str, bool], ...] = (
    ("matematicas", "Matemáticas", False),
    ("lengua_castellana", "Lengua castellana", False),
    ("ingles", "Inglés", False),
    ("biologia", "Ciencias naturales / Biología", False),
    ("quimica", "Química", False),
    ("fisica", "Física", False),
    ("sociales", "Ciencias sociales", False),
    ("tecnologia_informatica", "Tecnología e informática", False),
    ("artistica", "Educación artística", False),
    ("educacion_fisica", "Educación física", False),
    ("emprendimiento", "Emprendimiento", False),
    ("otra", "Otra", True),
)

ACTIVITIES: tuple[tuple[str, str, bool, bool], ...] = (
    ("deportes", "Deportes", False, False),
    ("musica", "Música", False, False),
    ("danza", "Danza", False, False),
    ("dibujo_diseno", "Dibujo / diseño", False, False),
    ("programacion_tecnologia", "Programación / tecnología", False, False),
    ("videojuegos", "Videojuegos", False, False),
    ("creacion_contenido", "Creación de contenido", False, False),
    ("lectura", "Lectura", False, False),
    ("escritura", "Escritura", False, False),
    ("voluntariado", "Voluntariado", False, False),
    ("emprendimiento_ventas", "Emprendimiento / ventas", False, False),
    ("comunitaria", "Actividades comunitarias", False, False),
    ("reparacion_construccion", "Reparación / construcción", False, False),
    ("ninguna", "Ninguna", True, False),
    ("otra", "Otra", False, True),
)


class CatalogSeedError(RuntimeError):
    """El catálogo existente contradice la versión congelada esperada."""


def _assert_equal(
    *,
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    """Impide sobrescribir silenciosamente un catálogo ya versionado."""

    if actual != expected:
        raise CatalogSeedError(
            f"{label} no coincide con la definición congelada. "
            f"Actual={actual!r}; esperado={expected!r}."
        )


def _seed_dimensions(summary: dict[str, int]) -> None:
    for code, name_en, name_es, order in RIASEC_DIMENSIONS:
        dimension = db.session.get(RiasecDimension, code)
        if dimension is None:
            db.session.add(
                RiasecDimension(
                    code=code,
                    name_en=name_en,
                    name_es=name_es,
                    display_order=order,
                )
            )
            summary["riasec_dimensions_created"] += 1
            continue

        _assert_equal(
            label=f"RiasecDimension[{code}].name_en",
            actual=dimension.name_en,
            expected=name_en,
        )
        _assert_equal(
            label=f"RiasecDimension[{code}].name_es",
            actual=dimension.name_es,
            expected=name_es,
        )
        _assert_equal(
            label=f"RiasecDimension[{code}].display_order",
            actual=dimension.display_order,
            expected=order,
        )


def _seed_instrument(summary: dict[str, int]) -> InstrumentVersion:
    instrument = db.session.execute(
        select(Instrument).where(Instrument.code == INSTRUMENT_CODE)
    ).scalar_one_or_none()

    if instrument is None:
        instrument = Instrument(
            code=INSTRUMENT_CODE,
            name="O*NET Interest Profiler Short Form",
            source_name="O*NET Web Services",
            source_url=(
                "https://services.onetcenter.org/reference/mpp/ip/ip_questions"
            ),
            license_name="O*NET Tools Developer License",
            license_url="https://www.onetcenter.org/license_tools.html",
        )
        db.session.add(instrument)
        db.session.flush()
        summary["instruments_created"] += 1
    else:
        _assert_equal(
            label="Instrument.name",
            actual=instrument.name,
            expected="O*NET Interest Profiler Short Form",
        )
        _assert_equal(
            label="Instrument.source_name",
            actual=instrument.source_name,
            expected="O*NET Web Services",
        )

    version = db.session.execute(
        select(InstrumentVersion).where(
            InstrumentVersion.code == INSTRUMENT_VERSION_CODE
        )
    ).scalar_one_or_none()

    local_content_hash = instrument_content_sha256(ONET_ITEMS)
    if local_content_hash != OFFICIAL_SOURCE_MANIFEST_SHA256:
        raise CatalogSeedError(
            "El manifiesto local del instrumento no coincide con la versión "
            "oficial O*NET previamente verificada."
        )

    if version is None:
        version = InstrumentVersion(
            instrument_id=instrument.id,
            code=INSTRUMENT_VERSION_CODE,
            language="es",
            total_items=60,
            retrieval_date=date(2026, 9, 8),
            source_hash_sha256=OFFICIAL_SOURCE_MANIFEST_SHA256,
            local_content_hash_sha256=local_content_hash,
            scoring_spec_sha256=SCORING_SPEC_SHA256,
            verification_status=INSTRUMENT_VERIFICATION_UNVERIFIED,
        )
        db.session.add(version)
        db.session.flush()
        summary["instrument_versions_created"] += 1
    else:
        _assert_equal(
            label="InstrumentVersion.instrument_id",
            actual=version.instrument_id,
            expected=instrument.id,
        )
        _assert_equal(
            label="InstrumentVersion.language",
            actual=version.language,
            expected="es",
        )
        _assert_equal(
            label="InstrumentVersion.total_items",
            actual=version.total_items,
            expected=60,
        )
        if version.source_hash_sha256 is None:
            version.source_hash_sha256 = OFFICIAL_SOURCE_MANIFEST_SHA256
        else:
            _assert_equal(
                label="InstrumentVersion.source_hash_sha256",
                actual=version.source_hash_sha256,
                expected=OFFICIAL_SOURCE_MANIFEST_SHA256,
            )

        if version.local_content_hash_sha256 is None:
            version.local_content_hash_sha256 = local_content_hash
        else:
            _assert_equal(
                label="InstrumentVersion.local_content_hash_sha256",
                actual=version.local_content_hash_sha256,
                expected=local_content_hash,
            )

        if version.scoring_spec_sha256 is None:
            version.scoring_spec_sha256 = SCORING_SPEC_SHA256
        else:
            _assert_equal(
                label="InstrumentVersion.scoring_spec_sha256",
                actual=version.scoring_spec_sha256,
                expected=SCORING_SPEC_SHA256,
            )

    return version


def _seed_onet_items(
    version: InstrumentVersion,
    summary: dict[str, int],
) -> None:
    for index, area, text in ONET_ITEMS:
        code = f"IP{index:02d}"
        item = db.session.execute(
            select(ONetItem).where(
                ONetItem.instrument_version_id == version.id,
                ONetItem.item_code == code,
            )
        ).scalar_one_or_none()

        if item is None:
            db.session.add(
                ONetItem(
                    instrument_version_id=version.id,
                    item_code=code,
                    item_index=index,
                    area=area,
                    question_text=text,
                )
            )
            summary["onet_items_created"] += 1
            continue

        _assert_equal(
            label=f"ONetItem[{code}].item_index",
            actual=item.item_index,
            expected=index,
        )
        _assert_equal(
            label=f"ONetItem[{code}].area",
            actual=item.area,
            expected=area,
        )
        _assert_equal(
            label=f"ONetItem[{code}].question_text",
            actual=item.question_text,
            expected=text,
        )


def _seed_interest_items(summary: dict[str, int]) -> None:
    for code, text, position in INTEREST_ITEMS:
        item = db.session.execute(
            select(InterestItem).where(InterestItem.code == code)
        ).scalar_one_or_none()

        if item is None:
            db.session.add(
                InterestItem(
                    code=code,
                    question_text=text,
                    position=position,
                )
            )
            summary["interest_items_created"] += 1
            continue

        _assert_equal(
            label=f"InterestItem[{code}].question_text",
            actual=item.question_text,
            expected=text,
        )
        _assert_equal(
            label=f"InterestItem[{code}].position",
            actual=item.position,
            expected=position,
        )


def _seed_subjects(summary: dict[str, int]) -> None:
    for code, name, allows_other_text in SUBJECTS:
        subject = db.session.execute(
            select(Subject).where(Subject.code == code)
        ).scalar_one_or_none()

        if subject is None:
            db.session.add(
                Subject(
                    code=code,
                    name=name,
                    allows_other_text=allows_other_text,
                )
            )
            summary["subjects_created"] += 1
            continue

        _assert_equal(
            label=f"Subject[{code}].name",
            actual=subject.name,
            expected=name,
        )
        _assert_equal(
            label=f"Subject[{code}].allows_other_text",
            actual=subject.allows_other_text,
            expected=allows_other_text,
        )


def _seed_activities(summary: dict[str, int]) -> None:
    for code, name, is_exclusive, allows_other_text in ACTIVITIES:
        activity = db.session.execute(
            select(Activity).where(Activity.code == code)
        ).scalar_one_or_none()

        if activity is None:
            db.session.add(
                Activity(
                    code=code,
                    name=name,
                    is_exclusive=is_exclusive,
                    allows_other_text=allows_other_text,
                )
            )
            summary["activities_created"] += 1
            continue

        _assert_equal(
            label=f"Activity[{code}].name",
            actual=activity.name,
            expected=name,
        )
        _assert_equal(
            label=f"Activity[{code}].is_exclusive",
            actual=activity.is_exclusive,
            expected=is_exclusive,
        )
        _assert_equal(
            label=f"Activity[{code}].allows_other_text",
            actual=activity.allows_other_text,
            expected=allows_other_text,
        )


def seed_catalogs() -> dict[str, int]:
    """Carga todos los catálogos faltantes en una sola transacción.

    Es idempotente: ejecutar el comando varias veces no duplica registros.
    Si encuentra un registro con la misma identidad pero contenido distinto,
    falla y hace rollback en lugar de sobrescribir una versión congelada.
    """

    summary = {
        "riasec_dimensions_created": 0,
        "instruments_created": 0,
        "instrument_versions_created": 0,
        "onet_items_created": 0,
        "interest_items_created": 0,
        "subjects_created": 0,
        "activities_created": 0,
    }

    try:
        _seed_dimensions(summary)
        db.session.flush()
        version = _seed_instrument(summary)
        _seed_onet_items(version, summary)
        _seed_interest_items(summary)
        _seed_subjects(summary)
        _seed_activities(summary)
        db.session.commit()
        return summary
    except Exception:
        db.session.rollback()
        raise


def get_catalog_status() -> dict[str, Any]:
    """Devuelve un diagnóstico compacto de catálogos requeridos."""

    counts = {
        "riasec_dimensions": int(
            db.session.execute(
                select(func.count()).select_from(RiasecDimension)
            ).scalar_one()
        ),
        "instruments": int(
            db.session.execute(
                select(func.count()).select_from(Instrument)
            ).scalar_one()
        ),
        "instrument_versions": int(
            db.session.execute(
                select(func.count()).select_from(InstrumentVersion)
            ).scalar_one()
        ),
        "onet_items": int(
            db.session.execute(
                select(func.count(ONetItem.id)).join(InstrumentVersion).where(
                    InstrumentVersion.code == INSTRUMENT_VERSION_CODE
                )
            ).scalar_one()
        ),
        "interest_items": int(
            db.session.execute(
                select(func.count()).select_from(InterestItem)
            ).scalar_one()
        ),
        "subjects": int(
            db.session.execute(select(func.count()).select_from(Subject)).scalar_one()
        ),
        "activities": int(
            db.session.execute(select(func.count()).select_from(Activity)).scalar_one()
        ),
    }

    expected = {
        "riasec_dimensions": 6,
        "instruments": 1,
        "instrument_versions": 1,
        "onet_items": 60,
        "interest_items": 12,
        "subjects": len(SUBJECTS),
        "activities": len(ACTIVITIES),
    }

    version = db.session.execute(
        select(InstrumentVersion).where(
            InstrumentVersion.code == INSTRUMENT_VERSION_CODE
        )
    ).scalar_one_or_none()

    return {
        "ready": all(counts[key] >= expected[key] for key in expected),
        "counts": counts,
        "expected_minimum": expected,
        "instrument_verification_status": (
            version.verification_status if version is not None else None
        ),
        "source_verification_status": (
            SOURCE_VERIFICATION_STATUS if version is not None else None
        ),
        "instrument_source_hash_sha256": (
            version.source_hash_sha256 if version is not None else None
        ),
        "instrument_local_content_hash_sha256": (
            version.local_content_hash_sha256 if version is not None else None
        ),
        "scoring_spec_sha256": (
            version.scoring_spec_sha256 if version is not None else None
        ),
    }


def get_public_catalogs() -> dict[str, Any]:
    """Serializa catálogos complementarios necesarios por el frontend."""

    interests = db.session.execute(
        select(InterestItem)
        .where(InterestItem.is_active.is_(True))
        .order_by(InterestItem.position.asc())
    ).scalars().all()
    subjects = db.session.execute(
        select(Subject)
        .where(Subject.is_active.is_(True))
        .order_by(Subject.name.asc())
    ).scalars().all()
    activities = db.session.execute(
        select(Activity)
        .where(Activity.is_active.is_(True))
        .order_by(Activity.name.asc())
    ).scalars().all()

    return {
        "interest_answer_options": [
            {"value": 1, "name": "Nada"},
            {"value": 2, "name": "Poco"},
            {"value": 3, "name": "Ni poco ni mucho"},
            {"value": 4, "name": "Bastante"},
            {"value": 5, "name": "Mucho"},
        ],
        "interests": [
            {
                "code": item.code,
                "text": item.question_text,
                "position": item.position,
            }
            for item in interests
        ],
        "subjects": [
            {
                "code": subject.code,
                "name": subject.name,
                "allows_other_text": subject.allows_other_text,
            }
            for subject in subjects
        ],
        "activities": [
            {
                "code": activity.code,
                "name": activity.name,
                "is_exclusive": activity.is_exclusive,
                "allows_other_text": activity.allows_other_text,
            }
            for activity in activities
        ],
    }
