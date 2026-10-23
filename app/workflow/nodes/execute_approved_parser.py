from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.parser_runtime import (
    ParserExecutionError,
    execute_declarative_parser,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def execute_approved_parser_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    node_input_state = {
        "run_id": state["run_id"],
        "file_id": state["file_id"],
        "filename": state["filename"],
        "parser_execution_authorized": (
            state.get(
                "parser_execution_authorized",
                False,
            )
        ),
        "parser_match_found": (
            state.get(
                "parser_match_found",
                False,
            )
        ),
        "matched_parser_id": (
            state.get("matched_parser_id")
        ),
        "matched_parser_name": (
            state.get(
                "matched_parser_name"
            )
        ),
        "matched_parser_version_id": (
            state.get(
                "matched_parser_version_id"
            )
        ),
        "matched_parser_version_number": (
            state.get(
                "matched_parser_version_number"
            )
        ),
        "matched_parser_approval_status": (
            state.get(
                "matched_parser_approval_status"
            )
        ),
        "matched_parser_status": (
            state.get(
                "matched_parser_status"
            )
        ),
        "matched_parser_spec": (
            state.get(
                "matched_parser_spec"
            )
        ),
    }

    try:
        parser_spec = state.get(
            "matched_parser_spec"
        )

        if parser_spec is None:
            raise ParserExecutionError(
                message=(
                    "Approved parser specification "
                    "is unavailable."
                ),
                guardrail_name=(
                    "APPROVED_PARSER_SPEC_REQUIRED"
                ),
            )

        execution_result = (
            execute_declarative_parser(
                stored_path=state[
                    "stored_path"
                ],
                parser_spec=parser_spec,
                parser_execution_authorized=(
                    state.get(
                        "parser_execution_authorized",
                        False,
                    )
                ),
                parser_match_found=(
                    state.get(
                        "parser_match_found",
                        False,
                    )
                ),
                matched_parser_approval_status=(
                    state.get(
                        "matched_parser_approval_status"
                    )
                ),
                matched_parser_status=(
                    state.get(
                        "matched_parser_status"
                    )
                ),
            )
        )

        node_output_state = {
            **execution_result,
            "current_node": (
                "execute_approved_parser"
            ),
            "workflow_status": (
                "PARSING_COMPLETED"
            ),
            "progress_percent": 80,
            "error_code": None,
            "error_message": None,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "execute_approved_parser"
                ),
                status="PASSED",
                public_message=(
                    "The approved declarative "
                    "parser executed successfully"
                ),
                guardrail_name=(
                    "APPROVED_DECLARATIVE_PARSER_ONLY"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=80,
            )

            database.commit()

        return node_output_state

    except ParserExecutionError as exception:
        error_details = {
            "guardrail_name": (
                exception.guardrail_name
            ),
            "message": exception.message,
            "row_number": (
                exception.row_number
            ),
            "column_name": (
                exception.column_name
            ),
        }

        node_output_state = {
            "parsed_records": [],
            "parsed_row_count": 0,
            "source_row_count": 0,
            "rejected_row_count": (
                1
                if exception.row_number
                is not None
                else 0
            ),
            "output_truncated": False,
            "parser_execution_summary": {
                "execution_mode": (
                    "DECLARATIVE_ALLOWLISTED"
                ),
                "dynamic_code_execution": False,
                "failure": error_details,
            },
            "current_node": (
                "execute_approved_parser"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 80,
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
                    "execute_approved_parser"
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
                progress_percent=80,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected approved-parser "
            f"execution failure: {exception}"
        )

        node_output_state = {
            "parsed_records": [],
            "parsed_row_count": 0,
            "source_row_count": 0,
            "rejected_row_count": 0,
            "output_truncated": False,
            "parser_execution_summary": {
                "execution_mode": (
                    "DECLARATIVE_ALLOWLISTED"
                ),
                "dynamic_code_execution": False,
            },
            "current_node": (
                "execute_approved_parser"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 80,
            "error_code": (
                "UNEXPECTED_PARSER_EXECUTION_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "execute_approved_parser"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected approved-parser "
                    "execution failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_PARSER_EXECUTION_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=80,
            )

            database.commit()

        return node_output_state
