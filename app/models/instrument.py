"""Modelos del instrumento, versiones e ítems de evaluación.

FASE 2 — Base de datos
----------------------
El texto oficial de O*NET se almacenará posteriormente como datos de catálogo.
Este módulo define la estructura necesaria para versionarlo y auditarlo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Devuelve una fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


class Instrument(db.Model):
    """Definición estable de un instrumento de evaluación."""

    __tablename__ = "instruments"

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
        db.String(150),
        nullable=False,
    )
    source_name = db.Column(
        db.String(150),
        nullable=False,
    )
    source_url = db.Column(
        db.Text,
        nullable=True,
    )
    license_name = db.Column(
        db.String(150),
        nullable=True,
    )
    license_url = db.Column(
        db.Text,
        nullable=True,
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

    versions = db.relationship(
        "InstrumentVersion",
        back_populates="instrument",
    )

    def __repr__(self) -> str:
        return f"<Instrument {self.code}>"


class InstrumentVersion(db.Model):
    """Versión congelada de un instrumento y su contenido."""

    __tablename__ = "instrument_versions"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    instrument_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
    )
    language = db.Column(
        db.String(10),
        nullable=False,
        default="es",
    )
    total_items = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    retrieval_date = db.Column(
        db.Date,
        nullable=True,
    )
    source_hash_sha256 = db.Column(
        db.String(64),
        nullable=True,
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

    instrument = db.relationship(
        "Instrument",
        back_populates="versions",
    )
    onet_items = db.relationship(
        "ONetItem",
        back_populates="instrument_version",
    )
    assessment_sessions = db.relationship(
        "AssessmentSession",
        back_populates="instrument_version",
    )

    __table_args__ = (
        db.CheckConstraint(
            "total_items > 0",
            name="ck_instrument_versions_total_items",
        ),
    )

    def __repr__(self) -> str:
        return f"<InstrumentVersion {self.code}>"


class ONetItem(db.Model):
    """Ítem del O*NET Interest Profiler asociado a una dimensión RIASEC."""

    __tablename__ = "onet_items"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    instrument_version_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("instrument_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_code = db.Column(
        db.String(10),
        nullable=False,
    )
    item_index = db.Column(
        db.SmallInteger,
        nullable=False,
    )
    area = db.Column(
        db.String(1),
        db.ForeignKey("riasec_dimensions.code", ondelete="RESTRICT"),
        nullable=False,
    )
    question_text = db.Column(
        db.Text,
        nullable=False,
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

    instrument_version = db.relationship(
        "InstrumentVersion",
        back_populates="onet_items",
    )
    dimension = db.relationship(
        "RiasecDimension",
        back_populates="onet_items",
    )
    responses = db.relationship(
        "ONetResponse",
        back_populates="item",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "instrument_version_id",
            "item_index",
            name="uq_onet_items_version_index",
        ),
        db.UniqueConstraint(
            "instrument_version_id",
            "item_code",
            name="uq_onet_items_version_code",
        ),
        db.CheckConstraint(
            "item_index > 0",
            name="ck_onet_items_item_index",
        ),
        db.Index("ix_onet_items_area", "area"),
    )

    def __repr__(self) -> str:
        return f"<ONetItem {self.item_code} area={self.area}>"


class InterestItem(db.Model):
    """Pregunta propia G01-G12 usada como predictor estructurado.

    Estos ítems no se etiquetan como RIASEC porque no constituyen un segundo
    instrumento psicométrico validado. Su objetivo es actuar como variables X.
    """

    __tablename__ = "interest_items"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code = db.Column(
        db.String(10),
        nullable=False,
        unique=True,
    )
    question_text = db.Column(
        db.Text,
        nullable=False,
    )
    position = db.Column(
        db.SmallInteger,
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

    responses = db.relationship(
        "InterestResponse",
        back_populates="item",
    )

    __table_args__ = (
        db.CheckConstraint(
            "position > 0",
            name="ck_interest_items_position",
        ),
    )

    def __repr__(self) -> str:
        return f"<InterestItem {self.code}>"
