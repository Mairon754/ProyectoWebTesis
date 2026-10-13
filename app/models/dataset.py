"""Modelos de releases científicos del dataset."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DatasetRelease(db.Model):
    """Versión congelada e inmutable del dataset experimental primario."""

    __tablename__ = "dataset_releases"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = db.Column(db.String(40), nullable=False, unique=True)
    status = db.Column(db.String(15), nullable=False, default="frozen")
    collection_phase = db.Column(db.String(10), nullable=False)
    contract_version = db.Column(db.String(60), nullable=False)
    target_protocol_version = db.Column(db.String(80), nullable=False)
    split_protocol_version = db.Column(db.String(80), nullable=False)
    train_ratio = db.Column(db.Numeric(6, 5), nullable=False)
    validation_ratio = db.Column(db.Numeric(6, 5), nullable=False)
    test_ratio = db.Column(db.Numeric(6, 5), nullable=False)
    instrument_version_code = db.Column(db.String(50), nullable=False)
    instrument_content_hash_sha256 = db.Column(db.String(64), nullable=False)
    scoring_spec_sha256 = db.Column(db.String(64), nullable=False)
    schema_hash_sha256 = db.Column(db.String(64), nullable=False)
    release_hash_sha256 = db.Column(db.String(64), nullable=False)
    record_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    frozen_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    members = db.relationship(
        "DatasetReleaseMember",
        back_populates="release",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DatasetReleaseMember.participant_code",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status = 'frozen'",
            name="ck_dataset_releases_status_frozen",
        ),
        db.CheckConstraint(
            "collection_phase IN ('pilot', 'final')",
            name="ck_dataset_releases_collection_phase",
        ),
        db.CheckConstraint(
            "record_count > 0",
            name="ck_dataset_releases_record_count_positive",
        ),
        db.CheckConstraint(
            "train_ratio > 0 AND validation_ratio > 0 AND test_ratio > 0",
            name="ck_dataset_releases_ratios_positive",
        ),
    )


class DatasetReleaseMember(db.Model):
    """Membresía y split congelados de un participante en un release."""

    __tablename__ = "dataset_release_members"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("dataset_releases.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_code = db.Column(db.String(20), nullable=False)
    split_name = db.Column(db.String(12), nullable=False)
    record_hash_sha256 = db.Column(db.String(64), nullable=False)
    record_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    release = db.relationship("DatasetRelease", back_populates="members")

    __table_args__ = (
        db.UniqueConstraint(
            "release_id",
            "participant_code",
            name="uq_dataset_release_participant_code",
        ),
        db.CheckConstraint(
            "split_name IN ('train', 'validation', 'test')",
            name="ck_dataset_release_members_split",
        ),
        db.Index("ix_dataset_release_members_release_id", "release_id"),
        db.Index("ix_dataset_release_members_split_name", "split_name"),
    )
