"""Modelos de catálogo y resultado RIASEC/Holland.

FASE 2 — Base de datos
----------------------
La lógica de puntuación NO vive aquí. Los cálculos se implementarán en
`app/services/riasec_service.py` durante la Fase 3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import ARRAY

from app.extensions import db


def utcnow() -> datetime:
    """Devuelve una fecha UTC consciente de zona horaria."""

    return datetime.now(timezone.utc)


class RiasecDimension(db.Model):
    """Catálogo central de las seis dimensiones RIASEC."""

    __tablename__ = "riasec_dimensions"

    code = db.Column(
        db.String(1),
        primary_key=True,
    )
    name_en = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
    )
    name_es = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
    )
    display_order = db.Column(
        db.SmallInteger,
        nullable=False,
        unique=True,
    )
    description = db.Column(
        db.Text,
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    onet_items = db.relationship(
        "ONetItem",
        back_populates="dimension",
    )

    __table_args__ = (
        db.CheckConstraint(
            "code IN ('R', 'I', 'A', 'S', 'E', 'C')",
            name="ck_riasec_dimensions_code",
        ),
        db.CheckConstraint(
            "display_order BETWEEN 1 AND 6",
            name="ck_riasec_dimensions_display_order",
        ),
    )

    def __repr__(self) -> str:
        return f"<RiasecDimension {self.code}>"


class RiasecResult(db.Model):
    """Resultado RIASEC materializado para una sesión finalizada.

    Los seis puntajes se almacenan junto con una versión del algoritmo para
    conservar trazabilidad y reproducibilidad. Las respuestas O*NET siguen
    siendo la evidencia primaria a partir de la cual se calcula el resultado.
    """

    __tablename__ = "riasec_results"

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

    score_r = db.Column(db.SmallInteger, nullable=False)
    score_i = db.Column(db.SmallInteger, nullable=False)
    score_a = db.Column(db.SmallInteger, nullable=False)
    score_s = db.Column(db.SmallInteger, nullable=False)
    score_e = db.Column(db.SmallInteger, nullable=False)
    score_c = db.Column(db.SmallInteger, nullable=False)

    profile_1 = db.Column(db.String(1), nullable=True)
    profile_2 = db.Column(db.String(1), nullable=True)
    profile_3 = db.Column(db.String(1), nullable=True)
    holland_code = db.Column(db.String(3), nullable=True)

    tie_top1 = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    top1_candidates = db.Column(
        ARRAY(db.String(1)),
        nullable=True,
    )
    scoring_version = db.Column(
        db.String(30),
        nullable=False,
        default="RIASEC_SCORING_PROVISIONAL_V1",
    )
    calculated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    assessment_session = db.relationship(
        "AssessmentSession",
        back_populates="riasec_result",
    )

    __table_args__ = (
        db.CheckConstraint(
            "score_r BETWEEN 0 AND 40",
            name="ck_riasec_results_score_r",
        ),
        db.CheckConstraint(
            "score_i BETWEEN 0 AND 40",
            name="ck_riasec_results_score_i",
        ),
        db.CheckConstraint(
            "score_a BETWEEN 0 AND 40",
            name="ck_riasec_results_score_a",
        ),
        db.CheckConstraint(
            "score_s BETWEEN 0 AND 40",
            name="ck_riasec_results_score_s",
        ),
        db.CheckConstraint(
            "score_e BETWEEN 0 AND 40",
            name="ck_riasec_results_score_e",
        ),
        db.CheckConstraint(
            "score_c BETWEEN 0 AND 40",
            name="ck_riasec_results_score_c",
        ),
        db.CheckConstraint(
            "profile_1 IS NULL OR profile_1 IN ('R', 'I', 'A', 'S', 'E', 'C')",
            name="ck_riasec_results_profile_1",
        ),
        db.CheckConstraint(
            "profile_2 IS NULL OR profile_2 IN ('R', 'I', 'A', 'S', 'E', 'C')",
            name="ck_riasec_results_profile_2",
        ),
        db.CheckConstraint(
            "profile_3 IS NULL OR profile_3 IN ('R', 'I', 'A', 'S', 'E', 'C')",
            name="ck_riasec_results_profile_3",
        ),
        db.CheckConstraint(
            "holland_code IS NULL OR holland_code ~ '^[RIASEC]{3}$'",
            name="ck_riasec_results_holland_code",
        ),
        db.Index("ix_riasec_results_profile_1", "profile_1"),
        db.Index("ix_riasec_results_holland_code", "holland_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<RiasecResult session_id={self.session_id} "
            f"holland_code={self.holland_code}>"
        )
