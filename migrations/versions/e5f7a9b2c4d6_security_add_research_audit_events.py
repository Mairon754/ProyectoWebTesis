"""security: add research audit events

Revision ID: e5f7a9b2c4d6
Revises: d4e8f6a1c2b3
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f7a9b2c4d6"
down_revision = "d4e8f6a1c2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_username", sa.String(length=100), nullable=False),
        sa.Column("actor_role", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_role IN ('viewer', 'data_manager')",
            name="ck_research_audit_events_actor_role",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_research_audit_events_actor_username"),
        "research_audit_events",
        ["actor_username"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_audit_events_action"),
        "research_audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_audit_events_created_at"),
        "research_audit_events",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_research_audit_events_created_at"),
        table_name="research_audit_events",
    )
    op.drop_index(
        op.f("ix_research_audit_events_action"),
        table_name="research_audit_events",
    )
    op.drop_index(
        op.f("ix_research_audit_events_actor_username"),
        table_name="research_audit_events",
    )
    op.drop_table("research_audit_events")
