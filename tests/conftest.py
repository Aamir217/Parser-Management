import shutil
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.database import (
    drop_database_tables,
    initialize_database,
)


@pytest.fixture(
    scope="session",
    autouse=True,
)
def prepare_test_environment():
    """
    Create the SQLite tables before any test runs.

    The fixture is automatically applied to the
    complete pytest session.
    """

    upload_directory = Path(
        settings.upload_directory
    )

    output_directory = Path(
        settings.output_directory
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    drop_database_tables()
    initialize_database()

    yield

    # Keep the database after the tests temporarily
    # so failures can be inspected. Uploaded test
    # files are removed to keep the next run clean.
    if upload_directory.exists():
        shutil.rmtree(
            upload_directory
        )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
