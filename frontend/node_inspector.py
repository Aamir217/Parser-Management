from typing import Any

import streamlit as st

from frontend.node_metadata import (
    get_node_badge,
    get_node_metadata,
)


def find_execution_by_id(
    *,
    executions: list[dict[str, Any]],
    execution_id: Any,
) -> dict[str, Any] | None:
    """
    Find a node execution by database execution ID.
    """

    for execution in executions:
        if str(
            execution.get("id")
        ) == str(execution_id):
            return execution

    return None


def render_node_inspector(
    execution: dict[str, Any],
) -> None:
    """
    Render one workflow node using the same input and
    output state inspector for every node, including
    the LLM Parser Proposal node.
    """

    node_name = str(
        execution.get(
            "node_name",
            "unknown_node",
        )
    )

    metadata = get_node_metadata(
        node_name
    )

    node_label = metadata[
        "label"
    ]

    node_description = metadata[
        "description"
    ]

    node_category = metadata[
        "category"
    ]

    node_badge = get_node_badge(
        execution
    )

    st.markdown(
        f"### {node_label}"
    )

    st.caption(
        node_description
    )

    summary_columns = st.columns(4)

    summary_columns[0].metric(
        "Sequence",
        execution.get(
            "sequence_number",
            "Unavailable",
        ),
    )

    summary_columns[1].metric(
        "Status",
        execution.get(
            "status",
            "UNKNOWN",
        ),
    )

    summary_columns[2].metric(
        "Category",
        node_category,
    )

    summary_columns[3].metric(
        "Implementation",
        (
            node_badge
            or "Deterministic"
        ),
    )

    public_message = execution.get(
        "public_message"
    )

    if public_message:
        st.info(
            public_message
        )

    guardrail_name = execution.get(
        "guardrail_name"
    )

    if guardrail_name:
        st.write(
            "**Guardrail:**",
            guardrail_name,
        )

    input_state = execution.get(
        "input_state",
        {},
    ) or {}

    output_state = execution.get(
        "output_state",
        {},
    ) or {}

    input_column, output_column = (
        st.columns(2)
    )

    with input_column:
        st.markdown(
            "#### Input State"
        )

        if input_state:
            st.json(
                input_state,
                expanded=True,
            )
        else:
            st.info(
                "No input state was recorded."
            )

    with output_column:
        st.markdown(
            "#### Output State"
        )

        if output_state:
            st.json(
                output_state,
                expanded=True,
            )
        else:
            st.info(
                "No output state was recorded."
            )
