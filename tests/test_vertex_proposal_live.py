import json
import sys

from app.core.config import settings
from app.services.vertex_proposal_generator import (
    VertexProposalError,
    generate_vertex_parser_proposal,
)


def build_workbook_metadata() -> dict:
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
                "max_column": 4,
                "header_row": 1,
                "normalized_headers": [
                    "trade_id",
                    "trade_date",
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
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                    {
                        "position": 2,
                        "normalized_name": (
                            "trade_date"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                    {
                        "position": 3,
                        "normalized_name": (
                            "currency"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                    {
                        "position": 4,
                        "normalized_name": (
                            "amount"
                        ),
                        "inferred_type": (
                            "decimal"
                        ),
                        "sampled_non_null_count": 50,
                        "sampled_null_count": 0,
                    },
                ],
                "formula_count": 0,
                "merged_range_count": 0,
            }
        ],
    }


def build_canonical_schema() -> dict:
    return {
        "fingerprint_version": "1.0",
        "sheet_count": 1,
        "sheets": [
            {
                "position": 1,
                "normalized_name": (
                    "trade_data"
                ),
                "visibility": "visible",
                "header_row": 1,
                "columns": [
                    {
                        "position": 1,
                        "normalized_name": (
                            "trade_id"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "position": 2,
                        "normalized_name": (
                            "trade_date"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "position": 3,
                        "normalized_name": (
                            "currency"
                        ),
                        "inferred_type": (
                            "string"
                        ),
                    },
                    {
                        "position": 4,
                        "normalized_name": (
                            "amount"
                        ),
                        "inferred_type": (
                            "decimal"
                        ),
                    },
                ],
                "contains_formulas": False,
                "contains_merged_cells": False,
            }
        ],
    }


def main() -> None:
    print("Vertex proposal test configuration")
    print(
        "Project:",
        settings.google_cloud_project,
    )
    print(
        "Location:",
        settings.google_cloud_location,
    )
    print(
        "Model:",
        settings.vertex_model_name,
    )
    print(
        "Maximum output tokens:",
        settings.vertex_proposal_max_output_tokens,
    )

    proposal = generate_vertex_parser_proposal(
        workbook_metadata=(
            build_workbook_metadata()
        ),
        canonical_schema=(
            build_canonical_schema()
        ),
        schema_fingerprint="a" * 64,
        fingerprint_version="1.0",
    )

    print("\nGenerated proposal:")

    print(
        json.dumps(
            proposal,
            indent=2,
        )
    )

    assert (
        proposal["proposal_source"]
        == "VERTEX_AI"
    )

    assert (
        proposal["execution_allowed"]
        is False
    )

    assert (
        proposal["approval_required"]
        is True
    )

    parser_spec = proposal[
        "parser_spec"
    ]

    assert (
        parser_spec["source_sheet"]
        == "Trade Data"
    )

    assert parser_spec["header_row"] == 1

    mappings = parser_spec[
        "mappings"
    ]

    assert mappings

    available_columns = {
        "trade_id",
        "trade_date",
        "currency",
        "amount",
    }

    proposed_sources = {
        mapping["source"]
        for mapping in mappings
    }

    assert proposed_sources.issubset(
        available_columns
    )

    allowed_transformations = {
        "identity",
        "trim",
        "upper",
        "lower",
        "parse_date",
        "parse_decimal",
    }

    proposed_transformations = {
        mapping["transform"]
        for mapping in mappings
    }

    assert (
        proposed_transformations
        .issubset(
            allowed_transformations
        )
    )

    assert len(
        proposed_sources
    ) == len(mappings)

    proposed_targets = [
        mapping["target"]
        for mapping in mappings
    ]

    assert len(
        proposed_targets
    ) == len(set(proposed_targets))

    print(
        "\nLive Vertex parser proposal "
        "test passed"
    )


def test_live_vertex_parser_proposal() -> None:
    main()


if __name__ == "__main__":
    try:
        main()

    except VertexProposalError as exception:
        print(
            "\nVertex proposal test failed",
            file=sys.stderr,
        )

        print(
            "Guardrail:",
            exception.guardrail_name,
            file=sys.stderr,
        )

        print(
            "Message:",
            exception.message,
            file=sys.stderr,
        )

        raise
