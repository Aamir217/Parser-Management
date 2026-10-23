from uuid import uuid4

import pytest

from app.core.database import SessionLocal
from app.models.database import WorkflowRun
from app.services.vertex_proposal_generator import (
    VertexProposalError,
)
from app.workflow.nodes import (
    generate_parser_proposal as proposal_node_module,
)


def workbook_metadata() -> dict:
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
                "max_row": 3,
                "max_column": 4,
                "header_row": 1,
                "raw_headers": [
                    "Trade ID",
                    "Trade Date",
                    "Currency",
                    "Amount",
                ],
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
                "merged_range_count": 0,
                "formula_count": 0,
            }
        ],
    }


def canonical_schema() -> dict:
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


def create_state() -> dict:
    run_id = str(uuid4())
    file_id = str(uuid4())

    with SessionLocal() as database:
        database.add(
            WorkflowRun(
                id=run_id,
                file_id=file_id,
                filename="trade_data.xlsx",
                status=(
                    "NO_APPROVED_PARSER_FOUND"
                ),
                current_node=(
                    "match_parser_registry"
                ),
                progress_percent=45,
                error_message=None,
            )
        )

        database.commit()

    return {
        "run_id": run_id,
        "file_id": file_id,
        "filename": "trade_data.xlsx",
        "schema_fingerprint": "a" * 64,
        "fingerprint_version": "1.0",
        "parser_match_found": False,
        "parser_execution_authorized": False,
        "canonical_schema": (
            canonical_schema()
        ),
        "workbook_metadata": (
            workbook_metadata()
        ),
        "current_node": (
            "match_parser_registry"
        ),
        "workflow_status": (
            "NO_APPROVED_PARSER_FOUND"
        ),
        "progress_percent": 45,
    }


def vertex_proposal() -> dict:
    return {
        "proposal_version": "1.0",
        "proposal_source": "VERTEX_AI",
        "schema_fingerprint": "a" * 64,
        "fingerprint_version": "1.0",
        "parser_name_suggestion": (
            "Trade Data Parser"
        ),
        "parser_spec": {
            "source_sheet": "Trade Data",
            "header_row": 1,
            "mappings": [
                {
                    "source": "trade_id",
                    "target": "trade_id",
                    "transform": "trim",
                    "required": True,
                },
                {
                    "source": "trade_date",
                    "target": "trade_date",
                    "transform": "parse_date",
                    "required": True,
                },
                {
                    "source": "currency",
                    "target": "currency",
                    "transform": "upper",
                    "required": True,
                },
                {
                    "source": "amount",
                    "target": "amount",
                    "transform": (
                        "parse_decimal"
                    ),
                    "required": True,
                },
            ],
            "assumptions": [
                (
                    "Trade Data contains "
                    "business records."
                )
            ],
            "description": (
                "Vertex-generated proposal "
                "for human review."
            ),
        },
        "mapping_rationales": [],
        "review_requirements": [
            "Confirm required fields."
        ],
        "confidence": 0.9,
        "risk_level": "MEDIUM",
        "proposal_notes": (
            "Human approval is required."
        ),
        "execution_allowed": False,
        "approval_required": True,
    }


def test_vertex_success_is_preserved(
    monkeypatch,
):
    state = create_state()

    monkeypatch.setattr(
        proposal_node_module.settings,
        "enable_llm_proposal",
        True,
    )

    monkeypatch.setattr(
        proposal_node_module.settings,
        (
            "enable_deterministic_"
            "proposal_fallback"
        ),
        True,
    )

    monkeypatch.setattr(
        proposal_node_module,
        "generate_vertex_parser_proposal",
        lambda **_: vertex_proposal(),
    )

    result = (
        proposal_node_module
        .generate_parser_proposal_node(
            state
        )
    )

    assert result["proposal_status"] == (
        "PENDING_REVIEW"
    )

    assert result["proposal_source"] == (
        "VERTEX_AI"
    )

    assert result[
        "parser_execution_authorized"
    ] is False

    assert result[
        "parser_proposal"
    ]["execution_allowed"] is False

    assert result[
        "parser_proposal"
    ]["approval_required"] is True


def test_vertex_failure_uses_fallback(
    monkeypatch,
):
    state = create_state()

    monkeypatch.setattr(
        proposal_node_module.settings,
        "enable_llm_proposal",
        True,
    )

    monkeypatch.setattr(
        proposal_node_module.settings,
        (
            "enable_deterministic_"
            "proposal_fallback"
        ),
        True,
    )

    def fail_vertex(**_):
        raise VertexProposalError(
            message=(
                "Simulated Vertex failure"
            ),
            guardrail_name=(
                "VERTEX_PROPOSAL_REQUEST_FAILED"
            ),
        )

    monkeypatch.setattr(
        proposal_node_module,
        "generate_vertex_parser_proposal",
        fail_vertex,
    )

    result = (
        proposal_node_module
        .generate_parser_proposal_node(
            state
        )
    )

    assert result["proposal_status"] == (
        "PENDING_REVIEW"
    )

    assert result["proposal_source"] == (
        "DETERMINISTIC_FALLBACK"
    )

    assert result[
        "parser_execution_authorized"
    ] is False

    proposal = result[
        "parser_proposal"
    ]

    assert proposal[
        "proposal_source"
    ] == "DETERMINISTIC_FALLBACK"

    assert proposal[
        "execution_allowed"
    ] is False

    assert proposal[
        "approval_required"
    ] is True

    assert proposal["fallback_reason"] == (
        "Simulated Vertex failure"
    )

    validation = result[
        "proposal_validation"
    ]

    warning = validation[
        "llm_generation_warning"
    ]

    assert warning["code"] == (
        "VERTEX_PROPOSAL_REQUEST_FAILED"
    )

    assert warning["message"] == (
        "Simulated Vertex failure"
    )


def test_vertex_failure_blocks_when_fallback_disabled(
    monkeypatch,
):
    state = create_state()

    monkeypatch.setattr(
        proposal_node_module.settings,
        "enable_llm_proposal",
        True,
    )

    monkeypatch.setattr(
        proposal_node_module.settings,
        (
            "enable_deterministic_"
            "proposal_fallback"
        ),
        False,
    )

    def fail_vertex(**_):
        raise VertexProposalError(
            message=(
                "Simulated Vertex failure"
            ),
            guardrail_name=(
                "VERTEX_PROPOSAL_REQUEST_FAILED"
            ),
        )

    monkeypatch.setattr(
        proposal_node_module,
        "generate_vertex_parser_proposal",
        fail_vertex,
    )

    result = (
        proposal_node_module
        .generate_parser_proposal_node(
            state
        )
    )

    assert result["workflow_status"] == (
        "BLOCKED"
    )

    assert result["proposal_status"] == (
        "BLOCKED"
    )

    assert result[
        "parser_execution_authorized"
    ] is False

    assert result["error_code"] == (
        "VERTEX_PROPOSAL_REQUEST_FAILED"
    )


def test_llm_disabled_uses_deterministic_proposal(
    monkeypatch,
):
    state = create_state()

    monkeypatch.setattr(
        proposal_node_module.settings,
        "enable_llm_proposal",
        False,
    )

    result = (
        proposal_node_module
        .generate_parser_proposal_node(
            state
        )
    )

    assert result["proposal_status"] == (
        "PENDING_REVIEW"
    )

    assert result["proposal_source"] == (
        "DETERMINISTIC"
    )

    assert result[
        "parser_execution_authorized"
    ] is False
