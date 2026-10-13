"""Pruebas del protocolo automático de calidad de datos."""

from __future__ import annotations

import pytest


def test_finalize_runs_automatic_quality_and_passes_structural_checks(
    assessment_builder,
):
    from app.services.quality_service import (
        AUTOMATIC_QUALITY_PROTOCOL_VERSION,
        latest_automatic_quality_check,
    )

    assessment = assessment_builder(fill=True, finalize=True)
    check = latest_automatic_quality_check(assessment.id)

    assert check is not None
    assert check.protocol_version == AUTOMATIC_QUALITY_PROTOCOL_VERSION
    assert check.status == "passed"
    assert check.blocker_count == 0
    assert check.warning_count == 1
    assert "t03_optional_text_present" in check.observations_json["warnings"]
    assert len(check.input_hash_sha256) == 64


def test_incomplete_session_is_blocked_by_automatic_quality(
    assessment_builder,
):
    from app.services.quality_service import run_automatic_quality_check

    assessment = assessment_builder(fill=False, finalize=False)
    check = run_automatic_quality_check(assessment)

    assert check.status == "blocked"
    assert check.blocker_count > 0
    blocker_codes = set(check.observations_json["blockers"])
    assert "session_completed" in blocker_codes
    assert "onet_exactly_60" in blocker_codes
    assert "riasec_result_present" in blocker_codes


def test_changed_data_makes_previous_automatic_quality_stale(
    assessment_builder,
):
    from app.extensions import db
    from app.services.quality_service import automatic_quality_state

    assessment = assessment_builder(fill=True, finalize=True)
    assert automatic_quality_state(assessment) == "passed"

    response = next(
        row for row in assessment.open_responses if row.prompt_code == "T01"
    )
    response.response_text = response.response_text + " Texto adicional."
    response.word_count = len(response.response_text.split())
    db.session.commit()

    assert automatic_quality_state(assessment) == "stale"


def test_ml_inclusion_requires_current_passed_automatic_quality(
    assessment_builder,
):
    from app.extensions import db
    from app.services.dataset_service import (
        DatasetServiceError,
        review_session_quality,
    )

    assessment = assessment_builder(fill=True, finalize=True)
    response = next(
        row for row in assessment.open_responses if row.prompt_code == "T02"
    )
    response.response_text = response.response_text + " Cambio posterior."
    response.word_count = len(response.response_text.split())
    db.session.commit()

    with pytest.raises(
        DatasetServiceError,
        match="control automático vigente",
    ):
        review_session_quality(
            assessment,
            quality_status="valid",
            included_ml=True,
            dataset_version="TEST_QC_V1",
        )
