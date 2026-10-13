"""Modelos de control automático de calidad de datos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutomaticQualityCheck(db.Model):
    """Resultado inmutable de un protocolo automático de calidad."""

    __tablename__ = "automatic_quality_checks"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_version = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(15), nullable=False)
    blocker_count = db.Column(db.Integer, nullable=False, default=0)
    warning_count = db.Column(db.Integer, nullable=False, default=0)
    checks_json = db.Column(db.JSON, nullable=False)
    observations_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="automatic_quality_checks",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "protocol_version",
            name="uq_automatic_quality_checks_session_protocol",
        ),
        db.CheckConstraint(
            "status IN ('passed', 'blocked')",
            name="ck_automatic_quality_checks_status",
        ),
        db.CheckConstraint(
            "blocker_count >= 0",
            name="ck_automatic_quality_checks_blocker_count",
        ),
        db.CheckConstraint(
            "warning_count >= 0",
            name="ck_automatic_quality_checks_warning_count",
        ),
        db.Index("ix_automatic_quality_checks_session_id", "session_id"),
        db.Index("ix_automatic_quality_checks_status", "status"),
        db.Index("ix_automatic_quality_checks_protocol", "protocol_version"),
    )
