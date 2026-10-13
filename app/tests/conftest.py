"""Fixtures compartidos de la Fase 12.

Los tests de integración exigen una base PostgreSQL separada. Nunca se usa la
base de desarrollo como fallback porque la suite crea y elimina tablas.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="session")
def app():
    test_database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not test_database_url:
        pytest.skip(
            "Define TEST_DATABASE_URL apuntando a una base PostgreSQL exclusiva "
            "de pruebas para ejecutar integración.",
        )

    development_url = os.getenv("DATABASE_URL", "").strip()
    if development_url and test_database_url == development_url:
        pytest.fail(
            "TEST_DATABASE_URL no puede ser igual a DATABASE_URL. "
            "Los tests nunca deben ejecutarse sobre la base de desarrollo."
        )

    database_name = (make_url(test_database_url).database or "").lower()
    if "test" not in database_name:
        pytest.fail(
            "Por seguridad, la base indicada en TEST_DATABASE_URL debe incluir "
            "'test' en su nombre, por ejemplo riasec_test_db."
        )

    from config import TestingConfig

    TestingConfig.SECRET_KEY = "pytest-riasec-secret-key"
    TestingConfig.SQLALCHEMY_DATABASE_URI = test_database_url

    from app import create_app
    from app.extensions import db
    from app.services.catalog_service import seed_catalogs

    flask_app = create_app("testing")
    flask_app.config.update(
        RESEARCHER_ACCOUNTS=[
            {
                "username": "investigador",
                "display_name": "Investigador de prueba",
                "password_hash": generate_password_hash("ClavePrueba123!"),
                "role": "data_manager",
            }
        ]
    )

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        seed_catalogs()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def db_context(app):
    """Contexto limpio preservando catálogos sembrados."""

    from app.extensions import db
    from app.models import Participant

    with app.app_context():
        db.session.execute(delete(Participant))
        db.session.commit()
        yield
        db.session.rollback()
        db.session.execute(delete(Participant))
        db.session.commit()
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def demographics() -> dict[str, Any]:
    return {
        "age": 17,
        "grade": 11,
        "institution_code": "INST_TEST",
        "municipality": "Tumaco",
        "zone": "urbana",
        "gender_self_reported": "prefiero_no_responder",
        "has_career_in_mind": "no_estoy_seguro",
        "career_in_mind_text": None,
        "device_type": "desktop",
    }


@pytest.fixture()
def assessment_builder(
    db_context,
    demographics,
) -> Callable[..., Any]:
    """Crea sesiones de prueba y opcionalmente llena el flujo completo."""

    from app.services.assessment_service import (
        CURRENT_CONSENT_VERSION,
        create_assessment,
        finalize_assessment,
        get_questions,
        register_interest_response,
        register_onet_response,
        replace_activity_selections,
        replace_subject_selections,
        save_open_response,
    )

    def build(
        *,
        fill: bool = False,
        finalize: bool = False,
        onet_raw: int = 4,
    ):
        assessment = create_assessment(
            demographics=demographics,
            consent_version=CURRENT_CONSENT_VERSION,
            consent_accepted=True,
            assent_accepted=True,
            guardian_consent_required=True,
            guardian_consent_reference="GUARD-TEST-001",
            collection_method="institutional",
        )

        if fill:
            questions = get_questions(assessment.id)
            for index, question in enumerate(questions, start=1):
                register_onet_response(
                    session_id=assessment.id,
                    item_id=question["id"],
                    response_raw=onet_raw,
                    response_time_ms=1000 + index,
                    tts_used=index == 1,
                )

            for index in range(1, 13):
                register_interest_response(
                    session_id=assessment.id,
                    item_code=f"G{index:02d}",
                    response_value=4,
                )

            replace_subject_selections(
                session_id=assessment.id,
                subject_codes=["matematicas", "tecnologia_informatica"],
            )
            replace_activity_selections(
                session_id=assessment.id,
                activity_codes=["programacion_tecnologia"],
            )
            save_open_response(
                session_id=assessment.id,
                prompt_code="T01",
                response_text=(
                    "Me gusta aprender tecnología, resolver problemas y crear "
                    "proyectos digitales durante mi tiempo libre."
                ),
            )
            save_open_response(
                session_id=assessment.id,
                prompt_code="T02",
                response_text=(
                    "Disfruté desarrollar un proyecto escolar porque pude "
                    "investigar, organizar información y construir una solución."
                ),
            )

        if finalize:
            if not fill:
                raise ValueError("finalize=True requiere fill=True.")
            assessment = finalize_assessment(assessment.id)

        return assessment

    return build
