from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.schema_fingerprint import (
    SchemaFingerprintError,
    generate_schema_fingerprint,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def create_fingerprint_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    """
    LangGraph fingerprint node.

    Input:
        Accumulated graph state containing
        workbook_metadata.

    Output:
        Only the state update created by this node.
    """

    node_input_state = dict(state)

    try:
        fingerprint_result = (
            generate_schema_fingerprint(
                workbook_metadata=state[
                    "workbook_metadata"
                ]
            )
        )

        node_output_state = {
            "canonical_schema": (
                fingerprint_result[
                   "canonical_schema"
                ]
            ),
            "canonical_schema_json": (
                fingerprint_result[
                    "canonical_schema_json"
                ]
            ),
            "schema_fingerprint": (
                fingerprint_result[
                    "schema_fingerprint"
                ]
            ),
            "fingerprint_version": (
                fingerprint_result[
                    "fingerprint_version"
                ]
            ),
            "current_node": (
                "create_fingerprint"
            ),
            "workflow_status": (
                "FINGERPRINT_COMPLETED"
            ),
            "progress_percent": 35,
            "error_code": None,
            "error_message": None,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "create_fingerprint"
                ),
                status="PASSED",
                public_message=(
                    "Canonical workbook schema "
                    "and deterministic SHA-256 "
                    "fingerprint were created"
                ),
                guardrail_name=(
                    "CANONICAL_SHA256_FINGERPRINT"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=35,
            )

            database.commit()

        return node_output_state

    except SchemaFingerprintError as exception:
        node_output_state = {
            "current_node": (
                "create_fingerprint"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 35,
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
                    "create_fingerprint"
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
                progress_percent=35,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected fingerprint-generation "
            f"failure: {exception}"
        )

        node_output_state = {
            "current_node": (
                "create_fingerprint"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 35,
            "error_code": (
                "UNEXPECTED_FINGERPRINT_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "create_fingerprint"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected schema "
                    "fingerprint failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_FINGERPRINT_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=35,
            )

            database.commit()

        return node_output_state
