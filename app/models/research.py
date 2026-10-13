"""Auditoría de acciones del módulo privado de investigación."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchAuditEvent(db.Model):
    """Evento inmutable de acceso o modificación de datos de investigación."""

    __tablename__ = "research_audit_events"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_username = db.Column(db.String(100), nullable=False, index=True)
    actor_role = db.Column(db.String(30), nullable=False)
    action = db.Column(db.String(50), nullable=False, index=True)
    resource_type = db.Column(db.String(40), nullable=False)
    resource_id = db.Column(db.String(100), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "actor_role IN ('viewer', 'data_manager')",
            name="ck_research_audit_events_actor_role",
        ),
    )
