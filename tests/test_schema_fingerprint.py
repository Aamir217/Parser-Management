import copy

import pytest

from app.services.schema_fingerprint import (
    SchemaFingerprintError,
    build_canonical_schema,
    generate_schema_fingerprint,
)


def create_metadata() -> dict:
    return {
        "inspection_version": "1.0",
        "sheet_count": 1,
        "hidden_sheet_count": 0,
        "total_formula_count": 0,
        "total_merged_range_count": 0,
        "sheets": [
            {
                "position": 1,
                "name": "Trade Data",
                "normalized_name": (
                    "trade_data"
                ),
                "visibility": "visible",
                "is_hidden": False,
                "max_row": 100,
                "max_column": 3,
                "header_row": 1,
                "raw_headers": [
                    "Trade ID",
                    "Currency",
                    "Amount",
                ],
                "normalized_headers": [
                    "trade_id",
                    "currency",
                    "amount",
                ],
                "column_profiles": [
                    {
                        "position": 1,
                        "normalized_name": (
                            "trade_id"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                        "observed_type_counts": {
                            "string": 50,
                        },
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                    {
                        "position": 2,
                        "normalized_name": (
                            "currency"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                        "observed_type_counts": {
                            "string": 50,
                        },
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                    {
                        "position": 3,
                        "normalized_name": (
                            "amount"
                        ),
                        "inferred_type": (
                            "decimal"
                        ),
                        "observed_type_counts": {
                            "decimal": 50,
                        },
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                ],
                "merged_range_count": 0,
                "merged_ranges": [],
                "merged_ranges_truncated": False,
                "formula_count": 0,
                "formula_cells": [],
                "formula_locations_truncated": False,
            }
        ],
    }


def test_fingerprint_is_deterministic():
    metadata = create_metadata()

    first = generate_schema_fingerprint(
        metadata
    )

    second = generate_schema_fingerprint(
        copy.deepcopy(metadata)
    )

    assert (
        first["schema_fingerprint"]
        == second["schema_fingerprint"]
    )

    assert (
        first["canonical_schema_json"]
        == second["canonical_schema_json"]
    )

    assert len(
        first["schema_fingerprint"]
    ) == 64


def test_row_count_does_not_change_fingerprint():
    first_metadata = create_metadata()
    second_metadata = create_metadata()

    first_metadata["sheets"][0][
        "max_row"
    ] = 100

    second_metadata["sheets"][0][
        "max_row"
    ] = 50_000

    first = generate_schema_fingerprint(
        first_metadata
    )

    second = generate_schema_fingerprint(
        second_metadata
    )

    assert (
        first["schema_fingerprint"]
        == second["schema_fingerprint"]
    )


def test_sample_counts_do_not_change_fingerprint():
    first_metadata = create_metadata()
    second_metadata = create_metadata()

    second_metadata["sheets"][0][
        "column_profiles"
    ][0]["observed_type_counts"] = {
        "string": 5,
        "null": 45,
    }

    second_metadata["sheets"][0][
        "column_profiles"
    ][0]["sampled_non_null_count"] = 5

    second_metadata["sheets"][0][
        "column_profiles"
    ][0]["sampled_null_count"] = 45

    first = generate_schema_fingerprint(
        first_metadata
    )

    second = generate_schema_fingerprint(
        second_metadata
    )

    assert (
        first["schema_fingerprint"]
        == second["schema_fingerprint"]
    )


def test_column_name_changes_fingerprint():
    first_metadata = create_metadata()
    second_metadata = create_metadata()

    second_metadata["sheets"][0][
        "normalized_headers"
    ][2] = "trade_amount"

    second_metadata["sheets"][0][
        "column_profiles"
    ][2]["normalized_name"] = (
        "trade_amount"
    )

    first = generate_schema_fingerprint(
        first_metadata
    )

    second = generate_schema_fingerprint(
        second_metadata
    )

    assert (
        first["schema_fingerprint"]
        != second["schema_fingerprint"]
    )


def test_column_order_changes_fingerprint():
    first_metadata = create_metadata()
    second_metadata = create_metadata()

    second_metadata["sheets"][0][
        "normalized_headers"
    ] = [
        "trade_id",
        "amount",
        "currency",
    ]

    first = generate_schema_fingerprint(
        first_metadata
    )

    second = generate_schema_fingerprint(
        second_metadata
    )

    assert (
        first["schema_fingerprint"]
        != second["schema_fingerprint"]
    )


def test_inferred_type_changes_fingerprint():
    first_metadata = create_metadata()
    second_metadata = create_metadata()

    second_metadata["sheets"][0][
        "column_profiles"
    ][2]["inferred_type"] = "string"

    first = generate_schema_fingerprint(
        first_metadata
    )

    second = generate_schema_fingerprint(
        second_metadata
    )

    assert (
        first["schema_fingerprint"]
        != second["schema_fingerprint"]
    )


def test_canonical_schema_excludes_row_count():
    metadata = create_metadata()

    canonical_schema = build_canonical_schema(
        metadata
    )

    canonical_sheet = (
        canonical_schema["sheets"][0]
    )

    assert "max_row" not in canonical_sheet
    assert "max_column" not in canonical_sheet
    assert "raw_headers" not in canonical_sheet
    assert "formula_cells" not in canonical_sheet
    assert "merged_ranges" not in canonical_sheet


def test_missing_sheets_are_rejected():
    with pytest.raises(
        SchemaFingerprintError
    ) as exception:
        generate_schema_fingerprint(
            {
                "sheets": [],
            }
        )

    assert (
        exception.value.guardrail_name
        == "WORKBOOK_SHEETS_REQUIRED"
    )
