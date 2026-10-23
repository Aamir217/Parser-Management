from frontend.node_inspector import (
    find_execution_by_id,
)
from frontend.node_metadata import (
    build_node_button_label,
    get_node_badge,
    get_node_label,
    get_node_metadata,
)


def test_llm_node_friendly_label():
    assert (
        get_node_label(
            "generate_parser_proposal"
        )
        == "LLM Parser Proposal"
    )


def test_llm_node_category():
    metadata = get_node_metadata(
        "generate_parser_proposal"
    )

    assert metadata[
        "category"
    ] == "LLM"


def test_vertex_ai_button_label():
    execution = {
        "node_name": (
            "generate_parser_proposal"
        ),
        "status": "PASSED",
        "output_state": {
            "proposal_source": (
                "VERTEX_AI"
            ),
        },
    }

    assert (
        build_node_button_label(
            execution
        )
        == (
            "✅ LLM Parser Proposal "
            "· Vertex AI"
        )
    )


def test_fallback_button_label():
    execution = {
        "node_name": (
            "generate_parser_proposal"
        ),
        "status": "PASSED",
        "output_state": {
            "proposal_source": (
                "DETERMINISTIC_FALLBACK"
            ),
        },
    }

    assert (
        build_node_button_label(
            execution
        )
        == (
            "✅ LLM Parser Proposal "
            "· Deterministic Fallback"
        )
    )


def test_normal_node_has_no_badge():
    execution = {
        "node_name": (
            "inspect_workbook"
        ),
        "status": "PASSED",
        "output_state": {},
    }

    assert (
        get_node_badge(
            execution
        )
        == ""
    )

    assert (
        build_node_button_label(
            execution
        )
        == "✅ Inspect Workbook"
    )


def test_find_execution_by_id():
    executions = [
        {
            "id": 10,
            "node_name": "inspect_workbook",
        },
        {
            "id": 11,
            "node_name": (
                "generate_parser_proposal"
            ),
        },
    ]

    result = find_execution_by_id(
        executions=executions,
        execution_id=11,
    )

    assert result is not None

    assert result[
        "node_name"
    ] == "generate_parser_proposal"


def test_unknown_node_remains_visible():
    assert (
        get_node_label(
            "future_workflow_node"
        )
        == "Future Workflow Node"
    )
