import json
from uuid import uuid4

import pytest

from app.core.database import SessionLocal
from app.models.database import (
    ParserDefinition,
    ParserVersion,
)
from app.services.parser_registry import (
    ParserRegistryError,
    find_exact_approved_parser,
    register_bootstrap_approved_parser,
    validate_parser_specification,
)


def valid_parser_spec() -> dict:
    return {
        "source_sheet": "Trade Data",
        "header_row": 1,
        "mappings": [
            {
                "source": "trade_id",
                "target": "trade_id",
                "transform": "identity",
                "required": True,
            },
            {
                "source": "amount",
                "target": "amount",
                "transform": "parse_decimal",
                "required": True,
            },
        ],
    }


def test_valid_parser_specification():
    validate_parser_specification(
        valid_parser_spec()
    )


def test_unapproved_transformation_is_rejected():
    parser_spec = valid_parser_spec()

    parser_spec["mappings"][0][
        "transform"
    ] = "execute_python"

    with pytest.raises(
        ParserRegistryError
    ) as exception:
        validate_parser_specification(
            parser_spec
        )

    assert (
        exception.value.guardrail_name
        == "ALLOWLISTED_TRANSFORMATION_ONLY"
    )


def test_no_match_returns_unauthorized():
    with SessionLocal() as database:
        result = find_exact_approved_parser(
            database=database,
            schema_fingerprint="a" * 64,
            fingerprint_version="1.0",
        )

    assert result[
        "parser_match_found"
    ] is False

    assert result[
        "parser_execution_authorized"
    ] is False


def test_approved_exact_match_authorizes_execution():
    fingerprint = "b" * 64

    with SessionLocal() as database:
        registration = (
            register_bootstrap_approved_parser(
                database=database,
                parser_name=(
                    f"Trade Parser {uuid4()}"
                ),
                description=(
                    "Test approved parser"
                ),
                schema_fingerprint=(
                    fingerprint
                ),
                fingerprint_version="1.0",
                canonical_schema_json=(
                    '{"test":true}'
                ),
                parser_spec=(
                    valid_parser_spec()
                ),
                created_by="pytest",
                approval_owner="pytest-approver",
            )
        )

        database.commit()

        assert registration[
            "approval_status"
        ] == "APPROVED"

        result = (
            find_exact_approved_parser(
                database=database,
                schema_fingerprint=(
                    fingerprint
                ),
                fingerprint_version="1.0",
            )
        )

    assert result[
        "parser_match_found"
    ] is True

    assert result[
        "parser_execution_authorized"
    ] is True

    assert result[
        "matched_parser_approval_status"
    ] == "APPROVED"

    assert result[
        "matched_parser_status"
    ] == "ACTIVE"


def test_pending_parser_does_not_authorize():
    fingerprint = "c" * 64

    with SessionLocal() as database:
        parser = ParserDefinition(
            id=str(uuid4()),
            parser_name=(
                f"Pending Parser {uuid4()}"
            ),
            description=(
                "Pending test parser"
            ),
            status="ACTIVE",
            created_by="pytest",
        )

        database.add(parser)
        database.flush()

        version = ParserVersion(
            id=str(uuid4()),
            parser_id=parser.id,
            version_number=1,
            status="ACTIVE",
            approval_status="PENDING",
            schema_fingerprint=(
                fingerprint
            ),
            fingerprint_version="1.0",
            canonical_schema_json=(
                '{"test":true}'
            ),
            parser_spec_json=json.dumps(
                valid_parser_spec()
            ),
            approval_owner=None,
            approved_at=None,
            created_by="pytest",
        )

        database.add(version)
        database.commit()

        result = (
            find_exact_approved_parser(
                database=database,
                schema_fingerprint=(
                    fingerprint
                ),
                fingerprint_version="1.0",
            )
        )

    assert result[
        "parser_match_found"
    ] is False

    assert result[
        "parser_execution_authorized"
    ] is False


def test_inactive_parser_does_not_authorize():
    fingerprint = "d" * 64

    with SessionLocal() as database:
        parser = ParserDefinition(
            id=str(uuid4()),
            parser_name=(
                f"Inactive Parser {uuid4()}"
            ),
            description=(
                "Inactive test parser"
            ),
            status="INACTIVE",
            created_by="pytest",
        )

        database.add(parser)
        database.flush()

        version = ParserVersion(
            id=str(uuid4()),
            parser_id=parser.id,
            version_number=1,
            status="ACTIVE",
            approval_status="APPROVED",
            schema_fingerprint=(
                fingerprint
            ),
            fingerprint_version="1.0",
            canonical_schema_json=(
                '{"test":true}'
            ),
            parser_spec_json=json.dumps(
                valid_parser_spec()
            ),
            approval_owner="pytest",
            approved_at=None,
            created_by="pytest",
        )

        database.add(version)
        database.commit()

        result = (
            find_exact_approved_parser(
                database=database,
                schema_fingerprint=(
                    fingerprint
                ),
                fingerprint_version="1.0",
            )
        )

    assert result[
        "parser_match_found"
    ] is False

    assert result[
        "parser_execution_authorized"
    ] is False
