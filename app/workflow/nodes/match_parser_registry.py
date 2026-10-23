from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.parser_registry import (
    ParserRegistryError,
    find_exact_approved_parser,
    no_match_result,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def match_parser_registry_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    node_input_state = {
        "run_id": state["run_id"],
        "file_id": state["file_id"],
        "filename": state["filename"],
        "schema_fingerprint": (
            state["schema_fingerprint"]
        ),
        "fingerprint_version": (
            state["fingerprint_version"]
        ),
        "parser_match_policy": (
            settings.parser_match_policy
        ),
        "match_requirement": (
            "Exact schema fingerprint, exact "
            "fingerprint version, active parser "
            "definition, active parser version, "
            "and approved parser version"
        ),
    }

    try:
        with SessionLocal() as database:
            match_result = (
                find_exact_approved_parser(
                    database=database,
                    schema_fingerprint=state[
                        "schema_fingerprint"
                    ],
                    fingerprint_version=state[
                        "fingerprint_version"
                    ],
                )
            )

        if match_result[
            "parser_match_found"
        ]:
            workflow_status = (
                "APPROVED_PARSER_FOUND"
            )

            public_message = (
                "An exact active and approved "
                "parser version was found. "
                "Execution authorization was granted."
            )

        else:
            workflow_status = (
                "NO_APPROVED_PARSER_FOUND"
            )

            public_message = (
                "No exact active and approved "
                "parser version was found. "
                "Execution authorization remains blocked."
            )

        node_output_state = {
            **match_result,
            "current_node": (
                "match_parser_registry"
            ),
            "workflow_status": (
                workflow_status
            ),
            "progress_percent": 45,
            "error_code": None,
            "error_message": None,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "match_parser_registry"
                ),
                status="PASSED",
                public_message=(
                    public_message
                ),
                guardrail_name=(
                    "EXACT_APPROVED_PARSER_ONLY"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=45,
            )

            database.commit()

        return node_output_state

    except ParserRegistryError as exception:
        node_output_state = {
            **no_match_result(),
            "current_node": (
                "match_parser_registry"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 45,
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
                    "match_parser_registry"
                ),
                status="BLOCKED",
                public_message=(
                    exception.message
                ),
                guardrail_name=(
                    exception.ardrail_name
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=45,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected parser-registry "
            f"matching failure: {exception}"
        )

        node_output_state = {
            **no_match_result(),
            "current_node": (
                "match_parser_registry"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 45,
            "error_code": (
                "UNEXPECTED_REGISTRY_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "match_parser_registry"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected parser-registry "
                    "matching failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_REGISTRY_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=45,
            )

            database.commit()

        return node_output_state
