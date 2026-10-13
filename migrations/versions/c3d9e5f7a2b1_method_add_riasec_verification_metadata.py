"""method: add RIASEC verification metadata

Revision ID: c3d9e5f7a2b1
Revises: b7f2c8d4a1e3
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d9e5f7a2b1"
down_revision = "b7f2c8d4a1e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "instrument_versions",
        sa.Column("local_content_hash_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "instrument_versions",
        sa.Column("scoring_spec_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "instrument_versions",
        sa.Column(
            "verification_status",
            sa.String(length=20),
            nullable=False,
            server_default="unverified",
        ),
    )
    op.create_check_constraint(
        "ck_instrument_versions_verification_status",
        "instrument_versions",
        "verification_status IN ('unverified', 'verified', 'rejected')",
    )
    op.alter_column(
        "instrument_versions",
        "verification_status",
        server_default=None,
    )


def downgrade():
    op.drop_constraint(
        "ck_instrument_versions_verification_status",
        "instrument_versions",
        type_="check",
    )
    op.drop_column("instrument_versions", "verification_status")
    op.drop_column("instrument_versions", "scoring_spec_sha256")
    op.drop_column("instrument_versions", "local_content_hash_sha256")
