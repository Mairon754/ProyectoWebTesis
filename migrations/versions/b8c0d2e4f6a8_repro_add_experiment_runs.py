"""repro: add experiment run manifests

Revision ID: b8c0d2e4f6a8
Revises: a7b9c1d3e5f7
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "b8c0d2e4f6a8"
down_revision = "a7b9c1d3e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_code", sa.String(length=40), nullable=False),
        sa.Column("protocol_version", sa.String(length=60), nullable=False),
        sa.Column("dataset_release_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version", sa.String(length=40), nullable=False),
        sa.Column("dataset_release_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("run_type", sa.String(length=20), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("hyperparameters_json", sa.JSON(), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("environment_json", sa.JSON(), nullable=False),
        sa.Column("requirements_sha256", sa.String(length=64), nullable=True),
        sa.Column("package_snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("code_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("code_branch", sa.String(length=120), nullable=True),
        sa.Column("git_dirty", sa.Boolean(), nullable=False),
        sa.Column("manifest_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "run_type IN ('training', 'inference', 'evaluation')",
            name="ck_experiment_runs_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('registered', 'completed', 'failed')",
            name="ck_experiment_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_release_id"],
            ["dataset_releases.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_hash_sha256"),
        sa.UniqueConstraint("run_code"),
    )
    op.create_index(
        op.f("ix_experiment_runs_dataset_release_id"),
        "experiment_runs",
        ["dataset_release_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_experiment_runs_dataset_release_id"),
        table_name="experiment_runs",
    )
    op.drop_table("experiment_runs")
