"""ethics: add collection phase to assessment sessions

Revision ID: b7f2c8d4a1e3
Revises: 0a66a2793374
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "b7f2c8d4a1e3"
down_revision = "0a66a2793374"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assessment_sessions",
        sa.Column(
            "collection_phase",
            sa.String(length=10),
            nullable=False,
            server_default="pilot",
        ),
    )
    op.create_check_constraint(
        "ck_assessment_sessions_collection_phase",
        "assessment_sessions",
        "collection_phase IN ('pilot', 'final')",
    )
    op.alter_column(
        "assessment_sessions",
        "collection_phase",
        server_default=None,
    )


def downgrade():
    op.drop_constraint(
        "ck_assessment_sessions_collection_phase",
        "assessment_sessions",
        type_="check",
    )
    op.drop_column("assessment_sessions", "collection_phase")
