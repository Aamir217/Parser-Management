from typing import Any

import streamlit as st

from frontend.node_inspector import (
    find_execution_by_id,
    render_node_inspector,
)
from frontend.node_metadata import (
    build_node_button_label,
)


def render_node_timeline(
    *,
    executions: list[dict[str, Any]],
) -> None:
    """
    Render all node executions using one consistent
    clickable timeline and inspector.

    The generate_parser_proposal execution appears as
    LLM Parser Proposal but remains a normal node.
    """

    st.markdown(
        "### Workflow nodes"
    )

    if not executions:
        st.info(
            "No workflow node executions "
            "are available."
        )
        return

    sorted_executions = sorted(
        executions,
        key=lambda execution: int(
            execution.get(
                "sequence_number",
                0,
            )
            or 0
        ),
    )

    node_columns = st.columns(
        min(
            3,
            max(
                1,
                len(sorted_executions),
            ),
        )
    )

    for index, execution in enumerate(
        sorted_executions
    ):
        column = node_columns[
            index % len(node_columns)
        ]

        execution_id = execution.get(
            "id"
        )

        with column:
            if st.button(
                build_node_button_label(
                    execution
                ),
                key=(
                    "workflow_node_"
                    f"{execution_id}_"
                    f"{execution.get('sequence_number')}"
                ),
                use_container_width=True,
            ):
                st.session_state[
                    "selected_execution_id"
                ] = execution_id

    selected_execution_id = (
        st.session_state.get(
            "selected_execution_id"
        )
    )

    selected_execution = None

    if selected_execution_id is not None:
        selected_execution = (
            find_execution_by_id(
                executions=(
                    sorted_executions
                ),
                execution_id=(
                    selected_execution_id
                ),
            )
        )

    if selected_execution is None:
        selected_execution = (
            sorted_executions[-1]
        )

        st.session_state[
            "selected_execution_id"
        ] = selected_execution.get(
            "id"
        )

    st.divider()

    render_node_inspector(
        selected_execution
    )
