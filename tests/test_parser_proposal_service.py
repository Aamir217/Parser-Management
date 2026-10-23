import json

import pytest

from app.services.parser_proposal_service import (
    ParserProposalError,
    calculate_proposal_hash,
    generate_deterministic_proposal,
    serialize_proposal,
    validate_generated_proposal,
)


def workbook_metadata() -> dict:
    return {
        "inspection_version": "1.0",
        "sheet_count": 1,
        "hidden_sheet_count": 0,
        "sheets": [
            {
                "position": 1,
                "name": "Trade Data",
                "normalized_name": (
                    "trade_data"
                ),
                "visibility": "visible",
                "is_hidden": False,
                "header_row": 1,
                "normalized_headers": [
                    "trade_id",
                    "trade_date",
                    "currency",
                    "amount",
                    "status",
                ],
                "column_profiles": [
                    {
                        "normalized_name": (
                            "trade_id"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "normalized_name": (
                            "trade_date"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "normalized_name": (
                            "currency"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "normalized_name": (
                            "amount"
                        ),
                        "inferred_type": (
                            "decimal"
                        ),
                    },
                    {
                        "normalized_name": (
                            "status"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                ],
            }
        ],
    }


def create_proposal() -> dict:
    return generate_deterministic_proposal(
        workbook_metadata=workbook_metadata(),
        schema_fingerprint="a" * 64,
        fingerprint_version="1.0",
    )


def test_deterministic_proposal_is_valid():
    proposal = create_proposal()

    validation = (
        validate_generated_proposal(
            proposal
        )
    )

    assert (
        proposal["proposal_source"]
        == "DETERMINISTIC"
    )

    assert (
        proposal["execution_allowed"]
        is False
    )

    assert (
        proposal["approval_required"]
        is True
    )

    assert (
        validation[
            "human_approval_required"
        ]
        is True
    )

    assert (
        validation["mapping_count"]
        == 5
    )


def test_proposal_transformations():
    proposal = create_proposal()

    mappings = {
        mapping["source"]:
        mapping["transform"]
        for mapping
        in proposal[
            "parser_spec"
        ]["mappings"]
    }

    assert mappings[
        "trade_id"
    ] == "trim"

    assert mappings[
        "trade_date"
    ] == "parse_date"

    assert mappings[
        "currency"
    ] == "upper"

    assert mappings[
        "amount"
    ] == "parse_decimal"

    assert mappings[
        "status"
    ] == "upper"


def test_proposal_hash_is_deterministic():
    first = create_proposal()
    second = create_proposal()

    first_json = serialize_proposal(
        first
    )

    second_json = serialize_proposal(
        second
    )

    assert first_json == second_json

    assert (
        calculate_proposal_hash(
            first_json
        )
        == calculate_proposal_hash(
            second_json
        )
    )


def test_proposal_cannot_authorize_execution():
    proposal = create_proposal()

    proposal["execution_allowed"] = True

    with pytest.raises(
        ParserProposalError
    ) as exception:
        validate_generated_proposal(
            proposal
        )

    assert (
        exception.value.guardrail_name
        == "UNAPPROVED_EXECUTION_BLOCKED"
    )


def test_proposal_requires_human_approval():
    proposal = create_proposal()

    proposal["approval_required"] = False

    with pytest.raises(
        ParserProposalError
    ) as exception:
        validate_generated_proposal(
            proposal
        )

    assert (
        exception.value.guardrail_name
        == "HUMAN_APPROVAL_REQUIRED"
    )
