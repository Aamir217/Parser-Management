from app.services import (
    vertex_proposal_generator
    as vertex_module,
)
from app.services.vertex_proposal_generator import (
    VertexProposalError,
    generate_vertex_parser_proposal_with_retry,
)


def test_retry_succeeds_after_empty_response(
    monkeypatch,
):
    attempts = {
        "count": 0,
    }

    def fake_generator(**_):
        attempts["count"] += 1

        if attempts["count"] < 3:
            raise VertexProposalError(
                message=(
                    "No structured proposal"
                ),
                guardrail_name=(
                    "STRUCTURED_LLM_OUTPUT_REQUIRED"
                ),
            )

        return {
            "proposal_source": "VERTEX_AI",
            "execution_allowed": False,
            "approval_required": True,
        }

    monkeypatch.setattr(
        vertex_module,
        "generate_vertex_parser_proposal",
        fake_generator,
    )

    monkeypatch.setattr(
        vertex_module.settings,
        "vertex_proposal_max_attempts",
        3,
    )

    monkeypatch.setattr(
        vertex_module.settings,
        (
            "vertex_proposal_"
            "retry_delay_seconds"
        ),
        0.0,
    )

    result = (
        generate_vertex_parser_proposal_with_retry(
            workbook_metadata={},
            canonical_schema={},
            schema_fingerprint="a" * 64,
            fingerprint_version="1.0",
        )
    )

    assert attempts["count"] == 3

    assert (
        result["proposal_source"]
        == "VERTEX_AI"
    )

    assert (
        result["vertex_attempt_number"]
        == 3
    )

    assert len(
        result["vertex_previous_errors"]
    ) == 2


def test_nonretryable_error_stops_immediately(
    monkeypatch,
):
    attempts = {
        "count": 0,
    }

    def fake_generator(**_):
        attempts["count"] += 1

        raise VertexProposalError(
            message="Unknown source column",
            guardrail_name=(
                "LLM_SOURCE_COLUMNS_EXIST"
            ),
        )

    monkeypatch.setattr(
        vertex_module,
        "generate_vertex_parser_proposal",
        fake_generator,
    )

    monkeypatch.setattr(
        vertex_module.settings,
        "vertex_proposal_max_attempts",
        3,
    )

    try:
        generate_vertex_parser_proposal_with_retry(
            workbook_metadata={},
            canonical_schema={},
            schema_fingerprint="a" * 64,
            fingerprint_version="1.0",
        )

    except VertexProposalError as exception:
        assert exception.guardrail_name == (
            "LLM_SOURCE_COLUMNS_EXIST"
        )

    else:
        raise AssertionError(
            "Expected VertexProposalError"
        )

    assert attempts["count"] == 1
