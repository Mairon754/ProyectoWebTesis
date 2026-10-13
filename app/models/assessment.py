"""Modelos de sesión de evaluación, preferencias y control de calidad.

FASE 2 — Base de datos
----------------------
Una `AssessmentSession` representa una aplicación concreta del instrumento.
Los datos contextuales se guardan como fotografía de esa sesión para no
sobrescribir información histórica del participante.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Devuelve una fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


class AssessmentSession(db.Model):
    """Aplicación individual del instrumento a un participante."""

    __tablename__ = "assessment_sessions"

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
    consent_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("consent_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_version_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("instrument_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    age = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    grade = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    institution_code = db.Column(
        db.String(30),
        nullable=False,
    )
    municipality = db.Column(
        db.String(100),
        nullable=False,
    )
    zone = db.Column(
        db.String(10),
        nullable=False,
    )
    gender_self_reported = db.Column(
        db.String(30),
        nullable=True,
    )
    has_career_in_mind = db.Column(
        db.String(20),
        nullable=False,
    )
    career_in_mind_text = db.Column(
        db.Text,
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="created",
    )
    current_stage = db.Column(
        db.String(30),
        nullable=False,
        default="demographics",
    )
    current_item_index = db.Column(
        db.SmallInteger,
        nullable=True,
    )

    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds = db.Column(
        db.Integer,
        nullable=True,
    )
    device_type = db.Column(
        db.String(15),
        nullable=False,
        default="unknown",
    )
    collection_phase = db.Column(
        db.String(10),
        nullable=False,
        default="pilot",
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

    participant = db.relationship(
        "Participant",
        back_populates="assessment_sessions",
    )
    consent_record = db.relationship(
        "ConsentRecord",
        back_populates="assessment_sessions",
    )
    instrument_version = db.relationship(
        "InstrumentVersion",
        back_populates="assessment_sessions",
    )
    onet_responses = db.relationship(
        "ONetResponse",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    interest_responses = db.relationship(
        "InterestResponse",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    subject_links = db.relationship(
        "SessionSubject",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    activity_links = db.relationship(
        "SessionActivity",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    open_responses = db.relationship(
        "OpenResponse",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    riasec_result = db.relationship(
        "RiasecResult",
        back_populates="assessment_session",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    quality_review = db.relationship(
        "DataQualityReview",
        back_populates="assessment_session",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    automatic_quality_checks = db.relationship(
        "AutomaticQualityCheck",
        back_populates="assessment_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AutomaticQualityCheck.created_at",
    )

    __table_args__ = (
        db.CheckConstraint(
            "age BETWEEN 14 AND 25",
            name="ck_assessment_sessions_age",
        ),
        db.CheckConstraint(
            "grade IN (10, 11)",
            name="ck_assessment_sessions_grade",
        ),
        db.CheckConstraint(
            "zone IN ('urbana', 'rural')",
            name="ck_assessment_sessions_zone",
        ),
        db.CheckConstraint(
            "gender_self_reported IS NULL OR "
            "gender_self_reported IN "
            "('mujer', 'hombre', 'no_binario', 'otro', "
            "'prefiero_no_responder')",
            name="ck_assessment_sessions_gender",
        ),
        db.CheckConstraint(
            "has_career_in_mind IN ('si', 'no', 'no_estoy_seguro')",
            name="ck_assessment_sessions_career_intent",
        ),
        db.CheckConstraint(
            "status IN ('created', 'in_progress', 'completed', 'abandoned')",
            name="ck_assessment_sessions_status",
        ),
        db.CheckConstraint(
            "current_stage IN "
            "('demographics', 'onet', 'interests', 'subjects', "
            "'activities', 'open_questions', 'results', 'completed')",
            name="ck_assessment_sessions_current_stage",
        ),
        db.CheckConstraint(
            "current_item_index IS NULL OR current_item_index BETWEEN 1 AND 60",
            name="ck_assessment_sessions_current_item_index",
        ),
        db.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_assessment_sessions_duration",
        ),
        db.CheckConstraint(
            "device_type IN ('mobile', 'tablet', 'desktop', 'unknown')",
            name="ck_assessment_sessions_device_type",
        ),
        db.CheckConstraint(
            "collection_phase IN ('pilot', 'final')",
            name="ck_assessment_sessions_collection_phase",
        ),
        db.Index("ix_assessment_sessions_status", "status"),
        db.Index(
            "ix_assessment_sessions_participant_started",
            "participant_id",
            "started_at",
        ),
    )

    @property
    def completed(self) -> bool:
        """Indica si la sesión alcanzó el estado final sin duplicar una columna."""

        return self.status == "completed"

    def __repr__(self) -> str:
        return f"<AssessmentSession {self.id} status={self.status}>"


class Subject(db.Model):
    """Catálogo de materias que el estudiante puede seleccionar."""

    __tablename__ = "subjects"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code = db.Column(
        db.String(40),
        nullable=False,
        unique=True,
    )
    name = db.Column(
        db.String(100),
        nullable=False,
    )
    allows_other_text = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
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

    session_links = db.relationship(
        "SessionSubject",
        back_populates="subject",
    )

    def __repr__(self) -> str:
        return f"<Subject {self.code}>"


class SessionSubject(db.Model):
    """Materia seleccionada dentro de una sesión."""

    __tablename__ = "session_subjects"

    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("subjects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    other_text = db.Column(
        db.String(150),
        nullable=True,
    )
    selected_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="subject_links",
    )
    subject = db.relationship(
        "Subject",
        back_populates="session_links",
    )

    __table_args__ = (
        db.Index("ix_session_subjects_subject_id", "subject_id"),
    )


class Activity(db.Model):
    """Catálogo de actividades realizadas fuera de clase."""

    __tablename__ = "activities"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code = db.Column(
        db.String(50),
        nullable=False,
        unique=True,
    )
    name = db.Column(
        db.String(120),
        nullable=False,
    )
    is_exclusive = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    allows_other_text = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
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

    session_links = db.relationship(
        "SessionActivity",
        back_populates="activity",
    )

    def __repr__(self) -> str:
        return f"<Activity {self.code}>"


class SessionActivity(db.Model):
    """Actividad seleccionada dentro de una sesión."""

    __tablename__ = "session_activities"

    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    activity_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("activities.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    other_text = db.Column(
        db.String(180),
        nullable=True,
    )
    selected_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="activity_links",
    )
    activity = db.relationship(
        "Activity",
        back_populates="session_links",
    )

    __table_args__ = (
        db.Index("ix_session_activities_activity_id", "activity_id"),
    )


class DataQualityReview(db.Model):
    """Decisión de inclusión/exclusión de una sesión para investigación."""

    __tablename__ = "data_quality_reviews"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    quality_status = db.Column(
        db.String(15),
        nullable=False,
        default="pending",
    )
    exclusion_reason = db.Column(
        db.Text,
        nullable=True,
    )
    included_ml = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    dataset_version = db.Column(
        db.String(30),
        nullable=True,
    )
    reviewed_at = db.Column(
        db.DateTime(timezone=True),
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
        back_populates="quality_review",
    )

    __table_args__ = (
        db.CheckConstraint(
            "quality_status IN ('pending', 'valid', 'excluded')",
            name="ck_data_quality_reviews_status",
        ),
        db.Index("ix_data_quality_reviews_included_ml", "included_ml"),
    )

    def __repr__(self) -> str:
        return (
            f"<DataQualityReview session_id={self.session_id} "
            f"status={self.quality_status}>"
        )
