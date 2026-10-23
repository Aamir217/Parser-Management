from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.models.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ParserProposal(Base):
    __tablename__ = "parser_proposals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
    )

    file_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )

    schema_fingerprint: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    fingerprint_version: Mapped[str] = mapped_column(
        String(20),
    )

    proposal_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING_REVIEW",
        index=True,
    )

    proposal_source: Mapped[str] = mapped_column(
        String(50),
        default="DETERMINISTIC",
    )

    proposal_json: Mapped[str] = mapped_column(
        Text,
    )

    proposal_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    validation_result_json: Mapped[str] = (
        mapped_column(
            Text,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )
