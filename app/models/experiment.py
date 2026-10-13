"""Registro reproducible de ejecuciones experimentales."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentRun(db.Model):
    """Manifiesto persistente de una ejecución sobre un release congelado."""

    __tablename__ = "experiment_runs"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    protocol_version = db.Column(db.String(60), nullable=False)
    dataset_release_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("dataset_releases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dataset_version = db.Column(db.String(40), nullable=False)
    dataset_release_hash_sha256 = db.Column(db.String(64), nullable=False)
    model_name = db.Column(db.String(120), nullable=False)
    model_version = db.Column(db.String(120), nullable=False)
    run_type = db.Column(db.String(20), nullable=False)
    seed = db.Column(db.Integer, nullable=True)
    hyperparameters_json = db.Column(db.JSON, nullable=False)
    conditions_json = db.Column(db.JSON, nullable=False)
    environment_json = db.Column(db.JSON, nullable=False)
    requirements_sha256 = db.Column(db.String(64), nullable=True)
    package_snapshot_sha256 = db.Column(db.String(64), nullable=False)
    code_commit_sha = db.Column(db.String(40), nullable=True)
    code_branch = db.Column(db.String(120), nullable=True)
    git_dirty = db.Column(db.Boolean, nullable=False, default=False)
    manifest_hash_sha256 = db.Column(db.String(64), nullable=False, unique=True)
    status = db.Column(db.String(15), nullable=False, default="registered")
    metrics_json = db.Column(db.JSON, nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    dataset_release = db.relationship("DatasetRelease")

    __table_args__ = (
        db.CheckConstraint(
            "run_type IN ('training', 'inference', 'evaluation')",
            name="ck_experiment_runs_run_type",
        ),
        db.CheckConstraint(
            "status IN ('registered', 'completed', 'failed')",
            name="ck_experiment_runs_status",
        ),
    )
