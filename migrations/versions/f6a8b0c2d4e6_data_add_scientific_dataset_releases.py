"""data: add scientific dataset releases

Revision ID: f6a8b0c2d4e6
Revises: e5f7a9b2c4d6
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a8b0c2d4e6"
down_revision = "e5f7a9b2c4d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dataset_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("collection_phase", sa.String(length=10), nullable=False),
        sa.Column("contract_version", sa.String(length=60), nullable=False),
        sa.Column("target_protocol_version", sa.String(length=80), nullable=False),
        sa.Column("split_protocol_version", sa.String(length=80), nullable=False),
        sa.Column("train_ratio", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("validation_ratio", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("test_ratio", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("instrument_version_code", sa.String(length=50), nullable=False),
        sa.Column("instrument_content_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("scoring_spec_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("release_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "collection_phase IN ('pilot', 'final')",
            name="ck_dataset_releases_collection_phase",
        ),
        sa.CheckConstraint(
            "record_count > 0",
            name="ck_dataset_releases_record_count_positive",
        ),
        sa.CheckConstraint(
            "train_ratio > 0 AND validation_ratio > 0 AND test_ratio > 0",
            name="ck_dataset_releases_ratios_positive",
        ),
        sa.CheckConstraint(
            "train_ratio + validation_ratio + test_ratio = 1",
            name="ck_dataset_releases_ratios_sum_one",
        ),
        sa.CheckConstraint(
            "status = 'frozen'",
            name="ck_dataset_releases_status_frozen",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_table(
        "dataset_release_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("participant_code", sa.String(length=20), nullable=False),
        sa.Column("split_name", sa.String(length=12), nullable=False),
        sa.Column("record_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("record_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "split_name IN ('train', 'validation', 'test')",
            name="ck_dataset_release_members_split",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["dataset_releases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "participant_code",
            name="uq_dataset_release_participant_code",
        ),
    )
    op.create_index(
        "ix_dataset_release_members_release_id",
        "dataset_release_members",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        "ix_dataset_release_members_split_name",
        "dataset_release_members",
        ["split_name"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_dataset_release_members_split_name",
        table_name="dataset_release_members",
    )
    op.drop_index(
        "ix_dataset_release_members_release_id",
        table_name="dataset_release_members",
    )
    op.drop_table("dataset_release_members")
    op.drop_table("dataset_releases")
