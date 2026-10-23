import json

import pytest

from app.schemas.llm_parser_proposal import (
    LlmParserProposalResponse,
)
from app.services.vertex_proposal_generator import (
    VertexProposalError,
    build_llm_schema_context,
    convert_llm_response_to_proposal,
    validate_llm_proposal_against_schema,
)


def workbook_metadata() -> dict:
    return {
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
                        "sampled_non_null_count": 2,
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
                        "sampled_non_null_count": 2,
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
                        "sampled_non_null_count": 2,
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
                        "sampled_non_null_count": 2,
                        "sampled_null_count": 0,
                    },
                ],
            }
        ],
    }


def model_response() -> (
    LlmParserProposalResponse
):
    return (
        LlmParserProposalResponse
        .model_validate(
            {
                "parser_name_suggestion": (
                    "Trade Data Parser"
                ),
                "source_sheet": (
                    "Trade Data"
                ),
                "header_row": 1,
                "mappings": [
                    {
                        "source": (
                            "trade_id"
                        ),
                        "target": (
                            "trade_id"
                        ),
                        "transform": "trim",
                        "required": True,
                        "rationale": (
                            "Primary trade identifier."
                        ),
                    },
                    {
                        "source": (
                            "trade_date"
                        ),
                        "target": (
                            "trade_date"
                        ),
                        "transform": (
                            "parse_date"
                        ),
                        "required": True,
                        "rationale": (
                            "Transaction date field."
                        ),
                    },
                    {
                        "source": (
                            "currency"
                        ),
                        "target": (
                            "currency"
                        ),
                        "transform": "upper",
                        "required": True,
                        "rationale": (
                            "Currency codes should "
                            "be uppercase."
                        ),
                    },
                    {
                        "source": "amount",
                        "target": "amount",
                        "transform": (
                            "parse_decimal"
                        ),
                        "required": True,
                        "rationale": (
                            "Monetary amount."
                        ),
                    },
                ],
                "assumptions": [
                    (
                        "Trade Data is the "
                        "business-data sheet."
                    )
                ],
                "review_requirements": [
                    (
                        "Confirm required fields."
                    )
                ],
                "confidence": 0.85,
                "risk_level": "MEDIUM",
                "proposal_notes": (
                    "Proposal requires "
                    "human approval."
                ),
            }
        )
    )


def test_context_excludes_business_values():
    context = build_llm_schema_context(
        workbook_metadata=(
            workbook_metadata()
        ),
        canonical_schema={
            "sheet_count": 1,
        },
        schema_fingerprint="a" * 64,
        fingerprint_version="1.0",
    )

    serialized = json.dumps(
        context
    )

    assert "stored_path" not in serialized
    assert "parsed_records" not in serialized
    assert "raw_headers" not in serialized
    assert "formula_cells" not in serialized


def test_valid_llm_proposal_matches_schema():
    response = model_response()

    validate_llm_proposal_against_schema(
        response=response,
        workbook_metadata=(
            workbook_metadata()
        ),
    )


def test_invented_column_is_rejected():
    response = model_response()

    response.mappings[0].source = (
        "invented_column"
    )

    with pytest.raises(
        VertexProposalError
    ) as exception:
        validate_llm_proposal_against_schema(
            response=response,
            workbook_metadata=(
                workbook_metadata()
            ),
        )

    assert (
        exception.value.guardrail_name
        == "LLM_SOURCE_COLUMNS_EXIST"
    )


def test_llm_response_is_proposal_only():
    proposal = (
        convert_llm_response_to_proposal(
            response=model_response(),
            schema_fingerprint="a" * 64,
            fingerprint_version="1.0",
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

    assert proposal["confidence"] == 0.85
