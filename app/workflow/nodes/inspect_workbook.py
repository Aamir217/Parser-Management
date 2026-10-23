from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.workbook_inspector import (
    WorkbookInspectionError,
    inspect_workbook_file,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def inspect_workbook_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    """
    Actual LangGraph node.

    Input:
        Current accumulated ParserWorkflowState.

    Output:
        Only this node's state update.

    The recorder stores:
        - the exact state entering the node
        - the exact state update returned by the node
    """

    node_input_state = dict(state)

    try:
        workbook_metadata = (
            inspect_workbook_file(
                stored_path=state["stored_path"]
            )
        )

        node_output_state = {
            "workbook_metadata": (
                workbook_metadata
            ),
            "current_node": (
                "inspect_workbook"
            ),
            "workflow_status": (
                "INSPECTION_COMPLETED"
            ),
            "progress_percent": 25,
            "error_code": None,
            "error_message": None,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "inspect_workbook"
                ),
                status="PASSED",
                public_message=(
                    "Workbook structure, headers, "
                    "formulas, merged cells and "
                    "sampled data types were inspected"
                ),
                guardrail_name=(
                    "DETERMINISTIC_WORKBOOK_INSPECTION"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=25,
            )

            database.commit()

        return node_output_state

    except WorkbookInspectionError as exception:
        node_output_state = {
            "current_node": (
                "inspect_workbook"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 25,
            "error_code": (
                exception.guardrail_name
            ),
            "error_message": (
                exception.message
            ),
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "inspect_workbook"
                ),
                status="BLOCKED",
                public_message=(
                    exception.message
                ),
                guardrail_name=(
                    exception.guardrail_name
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=25,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected workbook inspection "
            f"failure: {exception}"
        )

        node_output_state = {
            "current_node": (
                "inspect_workbook"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 25,
            "error_code": (
                "UNEXPECTED_INSPECTION_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "inspect_workbook"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected workbook "
                    "inspection failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_INSPECTION_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=25,
            )

            database.commit()

        return node_output_state
