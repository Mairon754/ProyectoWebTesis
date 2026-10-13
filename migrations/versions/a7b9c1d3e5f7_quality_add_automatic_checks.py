"""quality: add automatic data quality checks

Revision ID: a7b9c1d3e5f7
Revises: f6a8b0c2d4e6
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b9c1d3e5f7"
down_revision = "f6a8b0c2d4e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automatic_quality_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version", sa.String(length=60), nullable=False),
        sa.Column("input_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("observations_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "blocker_count >= 0",
            name="ck_automatic_quality_checks_blocker_count",
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'blocked')",
            name="ck_automatic_quality_checks_status",
        ),
        sa.CheckConstraint(
            "warning_count >= 0",
            name="ck_automatic_quality_checks_warning_count",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["assessment_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_automatic_quality_checks_session_id",
        "automatic_quality_checks",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_automatic_quality_checks_status",
        "automatic_quality_checks",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_automatic_quality_checks_protocol",
        "automatic_quality_checks",
        ["protocol_version"],
        unique=False,
    )
    op.create_index(
        "ix_automatic_quality_checks_session_protocol_created",
        "automatic_quality_checks",
        ["session_id", "protocol_version", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_automatic_quality_checks_session_protocol_created",
        table_name="automatic_quality_checks",
    )
    op.drop_index(
        "ix_automatic_quality_checks_protocol",
        table_name="automatic_quality_checks",
    )
    op.drop_index(
        "ix_automatic_quality_checks_status",
        table_name="automatic_quality_checks",
    )
    op.drop_index(
        "ix_automatic_quality_checks_session_id",
        table_name="automatic_quality_checks",
    )
    op.drop_table("automatic_quality_checks")
