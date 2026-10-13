"""Pruebas de reproducibilidad y manifiestos experimentales."""

from __future__ import annotations

import json

import pytest

from app.services.dataset_service import review_session_quality


def _pilot_release(assessment_builder):
    from app.services.dataset_release_service import freeze_dataset_release

    for index in range(5):
        assessment = assessment_builder(
            fill=True,
            finalize=True,
            onet_raw=2 + (index % 3),
        )
        review_session_quality(
            assessment,
            quality_status="valid",
            included_ml=True,
            dataset_version="EXPERIMENT_SOURCE_V1",
        )

    return freeze_dataset_release(
        version="EXPERIMENT_PILOT_V1",
        collection_phase="pilot",
        train_ratio="0.6",
        validation_ratio="0.2",
        test_ratio="0.2",
    )


def test_experiment_manifest_captures_dataset_code_environment_and_seed(
    assessment_builder,
):
    from app.services.experiment_service import (
        experiment_manifest,
        register_experiment_run,
    )

    release = _pilot_release(assessment_builder)
    run = register_experiment_run(
        run_code="RUN_TEST_001",
        dataset_version=release.version,
        model_name="transformer_custom",
        model_version="prototype-v1",
        run_type="training",
        seed=42,
        hyperparameters={"epochs": 3, "batch_size": 8},
        conditions={"device": "cpu", "validation_split": "validation"},
    )
    manifest = experiment_manifest(run)

    assert manifest["dataset_version"] == release.version
    assert manifest["dataset_release_hash_sha256"] == release.release_hash_sha256
    assert manifest["seed"] == 42
    assert manifest["hyperparameters"]["epochs"] == 3
    assert manifest["conditions"]["device"] == "cpu"
    assert len(manifest["manifest_hash_sha256"]) == 64
    assert len(manifest["package_snapshot_sha256"]) == 64
    assert manifest["environment"]["python_version"]
    assert isinstance(manifest["environment"]["packages"], dict)


def test_experiment_manifest_never_serializes_environment_secrets(
    assessment_builder,
    monkeypatch,
):
    from app.services.experiment_service import (
        experiment_manifest,
        register_experiment_run,
    )

    monkeypatch.setenv("VERY_PRIVATE_TOKEN", "never-store-this-value")
    release = _pilot_release(assessment_builder)
    run = register_experiment_run(
        run_code="RUN_TEST_002",
        dataset_version=release.version,
        model_name="model",
        model_version="v1",
        run_type="evaluation",
        seed=7,
        hyperparameters={},
        conditions={"device": "cpu"},
    )

    serialized = json.dumps(experiment_manifest(run), ensure_ascii=False)
    assert "never-store-this-value" not in serialized
    assert "VERY_PRIVATE_TOKEN" not in serialized


def test_experiment_registration_rejects_sensitive_json_keys(
    assessment_builder,
):
    from app.services.experiment_service import (
        ExperimentRunError,
        register_experiment_run,
    )

    release = _pilot_release(assessment_builder)
    with pytest.raises(ExperimentRunError, match="clave sensible"):
        register_experiment_run(
            run_code="RUN_TEST_003",
            dataset_version=release.version,
            model_name="remote-model",
            model_version="v1",
            run_type="inference",
            seed=None,
            hyperparameters={"api_token": "secret"},
            conditions={"device": "remote_api"},
        )


def test_experiment_run_can_close_once_with_metrics(
    assessment_builder,
):
    from app.services.experiment_service import (
        ExperimentRunError,
        complete_experiment_run,
        register_experiment_run,
    )

    release = _pilot_release(assessment_builder)
    register_experiment_run(
        run_code="RUN_TEST_004",
        dataset_version=release.version,
        model_name="model",
        model_version="v1",
        run_type="evaluation",
        seed=123,
        hyperparameters={},
        conditions={"test_split": "test"},
    )
    completed = complete_experiment_run(
        "RUN_TEST_004",
        metrics={"accuracy": 0.8, "latency_ms": 12.5},
    )

    assert completed.status == "completed"
    assert completed.metrics_json["accuracy"] == 0.8
    assert completed.completed_at is not None

    with pytest.raises(ExperimentRunError, match="ya fue cerrada"):
        complete_experiment_run(
            "RUN_TEST_004",
            metrics={"accuracy": 0.9},
        )
