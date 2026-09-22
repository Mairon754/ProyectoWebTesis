"""Modelos de respuestas del instrumento y preguntas complementarias.

FASE 2 — Base de datos
----------------------
Las respuestas O*NET se almacenan normalizadas: una fila por pregunta y
sesión. Esto facilita auditoría, autosave, modificaciones y exportación futura.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Computed

from app.extensions import db


def utcnow() -> datetime:
    """Devuelve una fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


class ONetResponse(db.Model):
    """Respuesta a un ítem oficial O*NET dentro de una sesión."""

    __tablename__ = "onet_responses"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("onet_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    response_raw = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    response_score = db.Column(
        db.SmallInteger,
        Computed("response_raw - 1", persisted=True),
        nullable=False,
    )
    response_time_ms = db.Column(
        db.Integer,
        nullable=True,
    )
    tts_used = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    changed_count = db.Column(
        db.SmallInteger,
        nullable=False,
        default=0,
    )
    answered_at = db.Column(
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

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="onet_responses",
    )
    item = db.relationship(
        "ONetItem",
        back_populates="responses",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "item_id",
            name="uq_onet_responses_session_item",
        ),
        db.CheckConstraint(
            "response_raw BETWEEN 1 AND 5",
            name="ck_onet_responses_response_raw",
        ),
        db.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_onet_responses_response_time_ms",
        ),
        db.CheckConstraint(
            "changed_count >= 0",
            name="ck_onet_responses_changed_count",
        ),
        db.Index("ix_onet_responses_session_id", "session_id"),
        db.Index("ix_onet_responses_item_id", "item_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ONetResponse session_id={self.session_id} "
            f"item_id={self.item_id} raw={self.response_raw}>"
        )


class InterestResponse(db.Model):
    """Respuesta a una pregunta propia G01-G12."""

    __tablename__ = "interest_responses"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    interest_item_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("interest_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    response_value = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    answered_at = db.Column(
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

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="interest_responses",
    )
    item = db.relationship(
        "InterestItem",
        back_populates="responses",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "interest_item_id",
            name="uq_interest_responses_session_item",
        ),
        db.CheckConstraint(
            "response_value BETWEEN 1 AND 5",
            name="ck_interest_responses_value",
        ),
        db.Index("ix_interest_responses_session_id", "session_id"),
        db.Index("ix_interest_responses_item_id", "interest_item_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<InterestResponse session_id={self.session_id} "
            f"value={self.response_value}>"
        )


class OpenResponse(db.Model):
    """Texto libre T01-T03 destinado a análisis NLP/Transformers."""

    __tablename__ = "open_responses"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_code = db.Column(
        db.String(3),
        nullable=False,
    )
    response_text = db.Column(
        db.Text,
        nullable=False,
    )
    word_count = db.Column(
        db.Integer,
        nullable=True,
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

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="open_responses",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "prompt_code",
            name="uq_open_responses_session_prompt",
        ),
        db.CheckConstraint(
            "prompt_code IN ('T01', 'T02', 'T03')",
            name="ck_open_responses_prompt_code",
        ),
        db.CheckConstraint(
            "word_count IS NULL OR word_count >= 0",
            name="ck_open_responses_word_count",
        ),
        db.Index("ix_open_responses_session_id", "session_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OpenResponse session_id={self.session_id} "
            f"prompt={self.prompt_code}>"
        )
