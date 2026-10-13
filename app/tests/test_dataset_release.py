"""Pruebas del contrato y congelación científica del dataset."""

from __future__ import annotations

import pytest

from app.services.dataset_service import review_session_quality


def _eligible_sessions(assessment_builder, count: int = 5):
    sessions = []
    for index in range(count):
        assessment = assessment_builder(
            fill=True,
            finalize=True,
            onet_raw=2 + (index % 3),
        )
        review_session_quality(
            assessment,
            quality_status="valid",
            included_ml=True,
            dataset_version="TEST_SOURCE_V1",
        )
        sessions.append(assessment)
    return sessions


def test_primary_contract_uses_same_text_x_and_keeps_targets_out_of_predictors(
    assessment_builder,
):
    from app.services.dataset_release_service import dataset_contract
    from app.services.dataset_service import build_primary_experiment_record

    assessment = assessment_builder(fill=True, finalize=True)
    record = build_primary_experiment_record(assessment)
    contract = dataset_contract()

    assert contract["predictor_columns"] == ["texto_combinado"]
    assert record["texto_combinado"]
    assert "score_r" in record
    assert "score_r" not in contract["predictor_columns"]
    assert "participant_code" not in contract["predictor_columns"]
    assert not any(key.lower().startswith("ip") for key in record)


def test_split_assignment_is_deterministic_and_participant_level():
    from app.services.dataset_release_service import assign_participant_splits

    codes = [f"RIA-{index:08X}" for index in range(10)]
    first = assign_participant_splits(
        codes,
        version="PILOT_V1",
        train_ratio="0.6",
        validation_ratio="0.2",
        test_ratio="0.2",
    )
    second = assign_participant_splits(
        list(reversed(codes)),
        version="PILOT_V1",
        train_ratio="0.6",
        validation_ratio="0.2",
        test_ratio="0.2",
    )

    assert first == second
    assert set(first) == set(codes)
    assert list(first.values()).count("train") == 6
    assert list(first.values()).count("validation") == 2
    assert list(first.values()).count("test") == 2


def test_split_ratios_must_be_explicit_and_sum_to_one():
    from app.services.dataset_release_service import (
        DatasetReleaseError,
        validate_split_ratios,
    )

    with pytest.raises(DatasetReleaseError, match="exactamente 1"):
        validate_split_ratios("0.7", "0.2", "0.2")


def test_pilot_release_freezes_records_splits_hashes_and_balance_report(
    assessment_builder,
):
    from app.services.dataset_release_service import (
        export_release_records,
        freeze_dataset_release,
        release_manifest,
    )

    _eligible_sessions(assessment_builder, count=5)
    release = freeze_dataset_release(
        version="RIASEC_PILOT_TEST_V1",
        collection_phase="pilot",
        train_ratio="0.6",
        validation_ratio="0.2",
        test_ratio="0.2",
    )
    manifest = release_manifest(release)
    records = export_release_records(release)

    assert release.record_count == 5
    assert len(release.release_hash_sha256) == 64
    assert len(release.schema_hash_sha256) == 64
    assert manifest["split_counts"] == {
        "test": 1,
        "train": 3,
        "validation": 1,
    }
    assert sum(manifest["profile_1_distribution"].values()) == 5
    assert "no se aplicó" in manifest["balance_note"]
    assert len(records) == 5
    assert all("split" in row for row in records)
    assert all("session_id" not in row for row in records)
    assert all("participant_code" not in row for row in records)
    assert all(str(row["record_id"]).startswith("RID-") for row in records)
    assert all(
        not any(key.lower().startswith("ip") for key in row)
        for row in records
    )


def test_final_release_remains_blocked_without_professional_verification(
    assessment_builder,
):
    from app.extensions import db
    from app.services.dataset_release_service import (
        DatasetReleaseError,
        freeze_dataset_release,
    )
    from app.services.quality_service import (
        automatic_quality_state,
        run_automatic_quality_check,
    )

    sessions = _eligible_sessions(assessment_builder, count=5)
    for assessment in sessions:
        assessment.collection_phase = "final"
    db.session.commit()

    # Fase 6: cambiar un dato incluido en el snapshot invalida el QC anterior.
    assert all(
        automatic_quality_state(assessment) == "stale"
        for assessment in sessions
    )

    # Al reevaluar como muestra final, la ausencia de validación profesional
    # queda registrada explícitamente como blocker del protocolo automático.
    checks = [
        run_automatic_quality_check(assessment)
        for assessment in sessions
    ]
    assert all(check.status == "blocked" for check in checks)
    assert all(
        "final_instrument_verified" in check.observations_json["blockers"]
        for check in checks
    )

    # Un release científico consume solo sesiones con QC vigente y aprobado;
    # por ello estas sesiones quedan fuera antes de llegar a la congelación.
    with pytest.raises(
        DatasetReleaseError,
        match="No hay sesiones elegibles",
    ):
        freeze_dataset_release(
            version="RIASEC_FINAL_TEST_V1",
            collection_phase="final",
            train_ratio="0.6",
            validation_ratio="0.2",
            test_ratio="0.2",
        )
