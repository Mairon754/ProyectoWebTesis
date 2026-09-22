"""Modelos relacionados con participantes y consentimiento.

FASE 2 — Base de datos
----------------------
Este módulo modela únicamente identidad anonimizada y evidencia de
consentimiento/asentimiento. No contiene lógica de negocio.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Devuelve una fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


class Participant(db.Model):
    """Participante anonimizado de la investigación."""

    __tablename__ = "participants"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    participant_code = db.Column(
        db.String(20),
        nullable=False,
        unique=True,
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    consent_records = db.relationship(
        "ConsentRecord",
        back_populates="participant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assessment_sessions = db.relationship(
        "AssessmentSession",
        back_populates="participant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Participant {self.participant_code}>"


class ConsentRecord(db.Model):
    """Registro de consentimiento y, cuando aplique, asentimiento."""

    __tablename__ = "consent_records"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    participant_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_version = db.Column(
        db.String(20),
        nullable=False,
    )
    consent_accepted = db.Column(
        db.Boolean,
        nullable=False,
    )
    assent_accepted = db.Column(
        db.Boolean,
        nullable=True,
    )
    guardian_consent_required = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    guardian_consent_reference = db.Column(
        db.String(100),
        nullable=True,
    )
    collection_method = db.Column(
        db.String(30),
        nullable=False,
        default="digital",
    )
    accepted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    participant = db.relationship(
        "Participant",
        back_populates="consent_records",
    )
    assessment_sessions = db.relationship(
        "AssessmentSession",
        back_populates="consent_record",
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "collection_method IN ('digital', 'paper', 'institutional')",
            name="ck_consent_records_collection_method",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ConsentRecord participant_id={self.participant_id} "
            f"version={self.consent_version}>"
        )
