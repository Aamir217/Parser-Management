from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    file_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="CREATED",
        index=True,
    )

    current_node: Mapped[str] = mapped_column(
        String(100),
        default="not_started",
    )

    progress_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
    )

    stored_filename: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )

    stored_path: Mapped[str] = mapped_column(
        String(1000),
    )

    extension: Mapped[str] = mapped_column(
        String(20),
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
    )

    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    validation_status: Mapped[str] = mapped_column(
        String(50),
        default="PASSED",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )


class NodeExecution(Base):
    __tablename__ = "node_executions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
    )

    node_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
    )

    public_message: Mapped[str] = mapped_column(
        String(500),
    )

    guardrail_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    input_state_json: Mapped[str] = mapped_column(
        Text,
    )

    output_state_json: Mapped[str] = mapped_column(
        Text,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class ParserDefinition(Base):
    __tablename__ = "parser_definitions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    parser_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        index=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(255),
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

    versions: Mapped[list["ParserVersion"]] = (
        relationship(
            back_populates="parser",
            cascade=(
                "all, delete-orphan"
            ),
        )
    )


class ParserVersion(Base):
    __tablename__ = "parser_versions"

    __table_args__ = (
        UniqueConstraint(
            "schema_fingerprint",
            "fingerprint_version",
            name=(
                "uq_parser_version_fingerprint"
            ),
        ),
        UniqueConstraint(
            "parser_id",
            "version_number",
            name=(
                "uq_parser_version_number"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    parser_id: Mapped[str] = mapped_column(
        ForeignKey(
            "parser_definitions.id"
        ),
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="DRAFT",
        index=True,
    )

    approval_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True,
    )

    schema_fingerprint: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    fingerprint_version: Mapped[str] = mapped_column(
        String(20),
    )

    canonical_schema_json: Mapped[str] = (
        mapped_column(
            Text,
        )
    )

    parser_spec_json: Mapped[str] = mapped_column(
        Text,
    )

    approval_owner: Mapped[str | None] = (
        mapped_column(
            String(255),
            nullable=True,
        )
    )

    approved_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(255),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    parser: Mapped[ParserDefinition] = (
        relationship(
            back_populates="versions"
        )
    )
