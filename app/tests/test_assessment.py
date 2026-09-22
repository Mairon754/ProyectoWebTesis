"""Pruebas de creación, respuestas, progreso y finalización."""

from __future__ import annotations

import pytest

from app.services.assessment_service import (
    AssessmentConflictError,
    AssessmentValidationError,
    get_progress,
    get_questions,
    register_onet_response,
    replace_activity_selections,
    replace_subject_selections,
)
from app.services.dataset_service import (
    build_research_dataset,
    review_session_quality,
)


def test_create_assessment_starts_anonymous_session(assessment_builder):
    assessment = assessment_builder()

    assert assessment.status == "in_progress"
    assert assessment.current_stage == "onet"
    assert assessment.current_item_index == 1
    assert assessment.participant.participant_code.startswith("RIA-")
    assert assessment.consent_record.consent_accepted is True


def test_response_upsert_updates_changed_count_and_progress(assessment_builder):
    assessment = assessment_builder()
    question = get_questions(assessment.id)[0]

    first = register_onet_response(
        session_id=assessment.id,
        item_id=question["id"],
        response_raw=3,
        response_time_ms=1500,
        tts_used=False,
    )
    second = register_onet_response(
        session_id=assessment.id,
        item_id=question["id"],
        response_raw=5,
        response_time_ms=1700,
        tts_used=True,
    )
    progress = get_progress(assessment.id)

    assert first.id == second.id
    assert second.response_raw == 5
    assert second.response_score == 4
    assert second.changed_count == 1
    assert second.tts_used is True
    assert progress["answered_items"] == 1
    assert progress["missing_items"] == 59


def test_selection_validations_are_enforced(assessment_builder):
    assessment = assessment_builder()

    with pytest.raises(AssessmentValidationError):
        replace_subject_selections(
            session_id=assessment.id,
            subject_codes=[
                "matematicas",
                "biologia",
                "fisica",
                "ingles",
            ],
        )

    with pytest.raises(AssessmentValidationError):
        replace_activity_selections(
            session_id=assessment.id,
            activity_codes=["ninguna", "programacion_tecnologia"],
        )


def test_finalize_requires_complete_flow(assessment_builder):
    from app.services.assessment_service import finalize_assessment

    assessment = assessment_builder()
    with pytest.raises(AssessmentValidationError):
        finalize_assessment(assessment.id)


def test_finalize_materializes_result_and_locks_responses(assessment_builder):
    assessment = assessment_builder(fill=True, finalize=True, onet_raw=4)
    progress = get_progress(assessment.id)

    assert assessment.status == "completed"
    assert assessment.current_stage == "completed"
    assert assessment.riasec_result is not None
    assert progress["onet_complete"] is True
    assert assessment.riasec_result.score_r == 30
    assert assessment.riasec_result.score_c == 30
    assert assessment.riasec_result.tie_top1 is True

    question = get_questions(assessment.id)[0]
    with pytest.raises(AssessmentConflictError):
        register_onet_response(
            session_id=assessment.id,
            item_id=question["id"],
            response_raw=5,
        )


def test_research_dataset_excludes_onet_items_from_ml_predictors(assessment_builder):
    assessment = assessment_builder(fill=True, finalize=True, onet_raw=4)
    review_session_quality(
        assessment,
        quality_status="valid",
        included_ml=True,
        dataset_version="RIASEC_TEST_V1",
    )

    rows = build_research_dataset("ml", {})

    assert len(rows) == 1
    assert rows[0]["participant_code"] == assessment.participant.participant_code
    assert not any(key.lower().startswith("ip") for key in rows[0])
    assert "score_r" in rows[0]
    assert "g01" in rows[0]
