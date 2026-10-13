"""Registro central de modelos SQLAlchemy.

Importar los modelos desde este módulo garantiza que Flask-Migrate/Alembic
pueda descubrir todas las tablas cuando genere migraciones.
"""

from .assessment import (
    Activity,
    AssessmentSession,
    DataQualityReview,
    SessionActivity,
    SessionSubject,
    Subject,
)
from .dataset import DatasetRelease, DatasetReleaseMember
from .experiment import ExperimentRun
from .instrument import Instrument, InstrumentVersion, InterestItem, ONetItem
from .participant import ConsentRecord, Participant
from .quality import AutomaticQualityCheck
from .responses import InterestResponse, ONetResponse, OpenResponse
from .research import ResearchAuditEvent
from .riasec import RiasecDimension, RiasecResult

__all__ = [
    "Activity",
    "AssessmentSession",
    "AutomaticQualityCheck",
    "ConsentRecord",
    "DataQualityReview",
    "DatasetRelease",
    "DatasetReleaseMember",
    "ExperimentRun",
    "Instrument",
    "InstrumentVersion",
    "InterestItem",
    "InterestResponse",
    "ONetItem",
    "ONetResponse",
    "OpenResponse",
    "Participant",
    "ResearchAuditEvent",
    "RiasecDimension",
    "RiasecResult",
    "SessionActivity",
    "SessionSubject",
    "Subject",
]
