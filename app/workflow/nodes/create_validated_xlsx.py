from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.validated_xlsx_writer import (
    ValidatedXlsxError,
    write_validated_xlsx,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def create_validated_xlsx_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    node_input_state = {
        "run_id": state["run_id"],
        "file_id": state["file_id"],
        "filename": state["filename"],
        "validation_status": (
            state.get(
                "validation_status"
            )
        ),
        "validation_summary": (
            state.get(
                "validation_summary"
            )
        ),
        "validation_metrics": (
            state.get(
                "validation_metrics"
            )
        ),
        "parsed_row_count": (
            state.get(
                "parsed_row_count",
                0,
            )
        ),
        "matched_parser_name": (
            state.get(
                "matched_parser_name"
            )
        ),
        "matched_parser_version_number": (
            state.get(
                "matched_parser_version_number"
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
            raise ValidatedXlsxError(
                message=(
                    "Approved parser specification "
                    "is unavailable."
                ),
                guardrail_name=(
                    "APPROVED_PARSER_SPEC_REQUIRED"
                ),
            )

        writer_result = write_validated_xlsx(
            run_id=state["run_id"],
            original_filename=state[
                "filename"
            ],
            parsed_records=state.get(
                "parsed_records",
                [],
            ),
            parser_spec=parser_spec,
            validation_status=state[
                "validation_status"
            ],
            validation_summary=state.get(
                "validation_summary",
                {},
            ),
            validation_metrics=state.get(
                "validation_metrics",
                {},
            ),
            validation_issues=state.get(
                "validation_issues",
                [],
            ),
        )

        node_output_state = {
            **writer_result,
            "current_node": (
                "create_validated_xlsx"
            ),
            "workflow_status": (
                "FINAL_FILE_READY"
            ),
            "progress_percent": 100,
            "error_code": None,
            "error_message": None,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "create_validated_xlsx"
                ),
                status="PASSED",
                public_message=(
                    "Final validated XLSX file "
                    "was created successfully"
                ),
                guardrail_name=(
                    "VALIDATED_OUTPUT_FILE_ONLY"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=100,
            )

            database.commit()

        return node_output_state

    except ValidatedXlsxError as exception:
        node_output_state = {
            "final_output_available": False,
            "final_output_filename": None,
            "final_output_size_bytes": 0,
            "final_output_row_count": 0,
            "final_output_column_count": 0,
            "final_output_checksum_sha256": None,
            "current_node": (
                "create_validated_xlsx"
            ),
            "workflow_status": (
                "FINAL_FILE_CREATION_FAILED"
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
                    "create_validated_xlsx"
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
            "Unexpected validated-XLSX "
            f"creation failure: {exception}"
        )

        node_output_state = {
            "final_output_available": False,
            "final_output_filename": None,
            "final_output_size_bytes": 0,
            "final_output_row_count": 0,
            "final_output_column_count": 0,
            "final_output_checksum_sha256": None,
            "current_node": (
                "create_validated_xlsx"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 100,
            "error_code": (
                "UNEXPECTED_XLSX_CREATION_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "create_validated_xlsx"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected validated-XLSX "
                    "creation failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_XLSX_CREATION_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=100,
            )

            database.commit()

        return node_output_state
