from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.output_validator import (
    OutputValidationError,
    validate_parsed_records,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def validate_parsed_output_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    node_input_state = {
        "run_id": state["run_id"],
        "file_id": state["file_id"],
        "filename": state["filename"],
        "matched_parser_id": (
            state.get(
                "matched_parser_id"
            )
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
        "matched_parser_spec": (
            state.get(
                "matched_parser_spec"
            )
        ),
        "parsed_records": (
            state.get(
                "parsed_records",
                [],
            )
        ),
        "parsed_row_count": (
            state.get(
                "parsed_row_count",
                0,
            )
        ),
        "source_row_count": (
            state.get(
                "source_row_count",
                0,
            )
        ),
        "rejected_row_count": (
            state.get(
                "rejected_row_count",
                0,
            )
        ),
        "output_truncated": (
            state.get(
                "output_truncated",
                False,
            )
        ),
    }

    try:
        parser_spec = state.get(
            "matched_parser_spec"
        )

        if not isinstance(
            parser_spec,
            dict,
        ):
            raise OutputValidationError(
                message=(
                    "Approved parser specification "
                    "is unavailable for validation."
                ),
                guardrail_name=(
                    "APPROVED_PARSER_SPEC_REQUIRED"
                ),
            )

        validation_result = (
            validate_parsed_records(
                parsed_records=state.get(
                    "parsed_records",
                    [],
                ),
                parser_spec=parser_spec,
                source_row_count=state.get(
                    "source_row_count",
                    0,
                ),
                parsed_row_count=state.get(
                    "parsed_row_count",
                    0,
                ),
                rejected_row_count=state.get(
                    "rejected_row_count",
                    0,
                ),
                output_truncated=state.get(
                    "output_truncated",
                    False,
                ),
            )
        )

        validation_status = (
            validation_result[
                "validation_status"
            ]
        )

        if validation_status == "PASS":
            workflow_status = (
                "WORKFLOW_COMPLETED"
            )

            node_status = "PASSED"

            public_message = (
                "Parsed output passed all "
                "deterministic validations"
            )

        elif validation_status == "WARN":
            workflow_status = (
                "WORKFLOW_COMPLETED_WITH_WARNINGS"
            )

            node_status = "PASSED"

            public_message = (
                "Parsed output completed with "
                "non-blocking validation warnings"
            )

        else:
            workflow_status = (
                "OUTPUT_VALIDATION_FAILED"
            )

            node_status = "BLOCKED"

            public_message = (
                "Parsed output failed "
                "deterministic validation"
            )

        node_output_state = {
            **validation_result,
            "current_node": (
                "validate_parsed_output"
            ),
            "workflow_status": (
                workflow_status
            ),
            "progress_percent": 100,
            "error_code": (
                None
                if validation_status
                in {"PASS", "WARN"}
                else "OUTPUT_VALIDATION_FAILED"
            ),
            "error_message": (
                None
                if validation_status
                in {"PASS", "WARN"}
                else (
                    "Parsed output did not pass "
                    "deterministic validation."
                )
            ),
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "validate_parsed_output"
                ),
                status=node_status,
                public_message=(
                    public_message
                ),
                guardrail_name=(
                    "DETERMINISTIC_OUTPUT_VALIDATION"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=100,
            )

            database.commit()

        return node_output_state

    except OutputValidationError as exception:
        node_output_state = {
            "validation_status": "FAIL",
            "validation_summary": {
                "message": exception.message,
                "error_count": 1,
                "warning_count": 0,
            },
            "validation_issues": [
                {
                    "severity": "ERROR",
                    "code": (
                        exception.guardrail_name
                    ),
                    "record_number": None,
                    "field": None,
                    "message": (
                        exception.message
                    ),
                }
            ],
            "validation_metrics": {},
            "duplicate_record_count": 0,
            "missing_required_value_count": 0,
            "invalid_value_count": 0,
            "current_node": (
                "validate_parsed_output"
            ),
            "workflow_status": (
                "OUTPUT_VALIDATION_FAILED"
            ),
            "progress_percent": 100,
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
                    "validate_parsed_output"
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
                progress_percent=100,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected output-validation "
            f"failure: {exception}"
        )

        node_output_state = {
            "validation_status": "FAIL",
            "validation_summary": {
                "message": error_message,
                "error_count": 1,
                "warning_count": 0,
            },
            "validation_issues": [],
            "validation_metrics": {},
            "duplicate_record_count": 0,
            "missing_required_value_count": 0,
            "invalid_value_count": 0,
            "current_node": (
                "validate_parsed_output"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 100,
            "error_code": (
                "UNEXPECTED_OUTPUT_VALIDATION_ERROR"
            ),
            "error_message": (
                error_message
            ),
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "validate_parsed_output"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected output-validation "
                    "failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_OUTPUT_VALIDATION_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=100,
            )

            database.commit()

        return node_output_state
