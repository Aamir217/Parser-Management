from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.config import settings

from app.models.database import (
    Base,
    NodeExecution,
    ParserDefinition,
    ParserVersion,
    UploadedFile,
    WorkflowRun,
)

# Importing this model registers its table
# with Base.metadata.
from app.models.parser_proposal import (
    ParserProposal,
)


connect_args: dict = {}

if settings.database_url.startswith(
    "sqlite"
):
    connect_args = {
        "check_same_thread": False,
    }


engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def initialize_database() -> None:
    Base.metadata.create_all(
        bind=engine
    )


def drop_database_tables() -> None:
    Base.metadata.drop_all(
        bind=engine
    )


def get_database_session() -> Generator[
    Session,
    None,
    None,
]:
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()
