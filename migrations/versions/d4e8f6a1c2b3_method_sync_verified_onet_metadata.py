"""method: synchronize verified O*NET scoring metadata

Revision ID: d4e8f6a1c2b3
Revises: c3d9e5f7a2b1
Create Date: 2026-10-13

This data migration records the intentional transition from the provisional
RIASEC scoring specification to the externally verified O*NET Short Form
specification. It only updates the known previous hash; unexpected values are
left untouched so seed-catalogs can still detect inconsistencies.
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e8f6a1c2b3"
down_revision = "c3d9e5f7a2b1"
branch_labels = None
depends_on = None


INSTRUMENT_VERSION_CODE = "IP_ES_60_V1"
LEGACY_SCORING_HASH = (
    "763e3cbbaa38a4a6e9b28b8d77cc34f37a31f90508eea41a0b0b2b0d81cc7d92"
)
VERIFIED_SCORING_HASH = (
    "182805c5cfe72623267d4e08df502e89de78e842c04c3905f05c4f16db318ec4"
)
VERIFIED_SOURCE_HASH = (
    "c30279b792fde80681f96f1c3108ccbedbcb7547dbdee29a90c2d48221433c43"
)


def upgrade():
    connection = op.get_bind()
    instrument_versions = sa.table(
        "instrument_versions",
        sa.column("code", sa.String),
        sa.column("source_hash_sha256", sa.String),
        sa.column("local_content_hash_sha256", sa.String),
        sa.column("scoring_spec_sha256", sa.String),
    )

    connection.execute(
        instrument_versions.update()
        .where(instrument_versions.c.code == INSTRUMENT_VERSION_CODE)
        .where(
            sa.or_(
                instrument_versions.c.scoring_spec_sha256 == LEGACY_SCORING_HASH,
                instrument_versions.c.scoring_spec_sha256.is_(None),
            )
        )
        .values(
            scoring_spec_sha256=VERIFIED_SCORING_HASH,
            source_hash_sha256=VERIFIED_SOURCE_HASH,
        )
    )


def downgrade():
    connection = op.get_bind()
    instrument_versions = sa.table(
        "instrument_versions",
        sa.column("code", sa.String),
        sa.column("source_hash_sha256", sa.String),
        sa.column("scoring_spec_sha256", sa.String),
    )

    connection.execute(
        instrument_versions.update()
        .where(instrument_versions.c.code == INSTRUMENT_VERSION_CODE)
        .where(instrument_versions.c.scoring_spec_sha256 == VERIFIED_SCORING_HASH)
        .where(instrument_versions.c.source_hash_sha256 == VERIFIED_SOURCE_HASH)
        .values(
            scoring_spec_sha256=LEGACY_SCORING_HASH,
            source_hash_sha256=None,
        )
    )
