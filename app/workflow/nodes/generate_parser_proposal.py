from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.parser_proposal_service import (
    ParserProposalError,
    calculate_proposal_hash,
    generate_deterministic_proposal,
    save_pending_proposal,
    serialize_proposal,
    validate_generated_proposal,
)
from app.services.vertex_proposal_generator import (
    VertexProposalError,
    generate_vertex_parser_proposal_with_retry,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def generate_parser_proposal_node(
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
        "parser_match_found": (
            state.get(
                "parser_match_found",
                False,
            )
        ),
        "parser_execution_authorized": (
            state.get(
                "parser_execution_authorized",
                False,
            )
        ),
        "canonical_schema": (
            state["canonical_schema"]
        ),
        "workbook_metadata": (
            state["workbook_metadata"]
        ),
        "llm_proposal_enabled": (
            settings.enable_llm_proposal
        ),
        "configured_model": (
            settings.vertex_model_name
        ),
    }

    try:
        if state.get(
            "parser_match_found"
        ) is True:
            raise ParserProposalError(
                message=(
                    "Proposal generation cannot run "
                    "for an already matched parser."
                ),
                guardrail_name=(
                    "UNKNOWN_FORMAT_REQUIRED"
                ),
            )

        if state.get(
            "parser_execution_authorized"
        ) is True:
            raise ParserProposalError(
                message=(
                    "Proposal generation cannot run "
                    "when execution is authorized."
                ),
                guardrail_name=(
                    "UNAUTHORIZED_PROPOSAL_PATH"
                ),
            )

        proposal_generation_warning = None

        if settings.enable_llm_proposal:
            try:
                proposal = (
                    generate_vertex_parser_proposal_with_retry(
                        workbook_metadata=state[
                            "workbook_metadata"
                        ],
                        canonical_schema=state[
                            "canonical_schema"
                        ],
                        schema_fingerprint=state[
                            "schema_fingerprint"
                        ],
                        fingerprint_version=state[
                            "fingerprint_version"
                        ],
                    )
                )

            except VertexProposalError as exception:
                if not (
                    settings
                    .enable_deterministic_proposal_fallback
                ):
                    raise ParserProposalError(
                        message=exception.message,
                        guardrail_name=(
                            exception.guardrail_name
                        ),
                    ) from exception

                proposal = (
                    generate_deterministic_proposal(
                        workbook_metadata=state[
                            "workbook_metadata"
                        ],
                        schema_fingerprint=state[
                            "schema_fingerprint"
                        ],
                        fingerprint_version=state[
                            "fingerprint_version"
                        ],
                    )
                )

                proposal[
                    "proposal_source"
                ] = "DETERMINISTIC_FALLBACK"

                proposal[
                    "fallback_reason"
                ] = exception.message

                proposal_generation_warning = {
                    "code": (
                        exception.guardrail_name
                    ),
                    "message": (
                        exception.message
                    ),
                }

        else:
            proposal = (
                generate_deterministic_proposal(
                    workbook_metadata=state[
                        "workbook_metadata"
                    ],
                    schema_fingerprint=state[
                        "schema_fingerprint"
                    ],
                    fingerprint_version=state[
                        "fingerprint_version"
                    ],
                )
            )

        validation_result = (
            validate_generated_proposal(
                proposal
            )
        )

        validation_result[
            "proposal_source"
        ] = proposal[
            "proposal_source"
        ]

        validation_result[
            "llm_generation_warning"
        ] = proposal_generation_warning

        proposal_json = serialize_proposal(
            proposal
        )

        proposal_hash = (
            calculate_proposal_hash(
                proposal_json
            )
        )

        with SessionLocal() as database:
            proposal_record = (
                save_pending_proposal(
                    database=database,
                    run_id=state["run_id"],
                    file_id=state["file_id"],
                    schema_fingerprint=state[
                        "schema_fingerprint"
                    ],
                    fingerprint_version=state[
                        "fingerprint_version"
                    ],
                    proposal=proposal,
                    validation_result=(
                        validation_result
                    ),
                )
            )

            proposal_source = proposal[
                "proposal_source"
            ]

            node_output_state = {
                "proposal_id": (
                    proposal_record.id
                ),
                "proposal_status": (
                    "PENDING_REVIEW"
                ),
                "proposal_source": (
                    proposal_source
                ),
                "parser_proposal": proposal,
                "proposal_hash": (
                    proposal_hash
                ),
                "proposal_validation": (
                    validation_result
                ),
                "parser_execution_authorized": (
                    False
                ),
                "current_node": (
                    "generate_parser_proposal"
                ),
                "workflow_status": (
                    "PROPOSAL_PENDING_REVIEW"
                ),
                "progress_percent": 60,
                "error_code": None,
                "error_message": None,
            }

            if proposal_source == "VERTEX_AI":
                public_message = (
                    "Vertex AI generated a "
                    "structured parser proposal, "
                    "which passed deterministic "
                    "validation and now requires "
                    "human review"
                )

                guardrail_name = (
                    "LLM_PROPOSAL_ONLY_NO_EXECUTION"
                )

            elif (
                proposal_source
                == "DETERMINISTIC_FALLBACK"
            ):
                public_message = (
                    "Vertex AI was unavailable or "
                    "returned an invalid proposal. "
                    "A deterministic fallback "
                    "proposal was created for "
                    "human review"
                )

                guardrail_name = (
                    "SAFE_PROPOSAL_FALLBACK"
                )

            else:
                public_message = (
                    "A deterministic parser "
                    "proposal was generated for "
                    "human review"
                )

                guardrail_name = (
                    "PROPOSAL_ONLY_NO_EXECUTION"
                )

            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "generate_parser_proposal"
                ),
                status="PASSED",
                public_message=(
                    public_message
                ),
                guardrail_name=(
                    guardrail_name
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=60,
            )

            database.commit()

        return node_output_state

    except ParserProposalError as exception:
        node_output_state = {
            "proposal_id": None,
            "proposal_status": "BLOCKED",
            "proposal_source": None,
            "parser_proposal": None,
            "proposal_hash": None,
            "proposal_validation": None,
            "parser_execution_authorized": False,
            "current_node": (
                "generate_parser_proposal"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 60,
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
                    "generate_parser_proposal"
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
                progress_percent=60,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        error_message = (
            "Unexpected proposal-generation "
            f"failure: {exception}"
        )

        node_output_state = {
            "proposal_id": None,
            "proposal_status": "FAILED",
            "proposal_source": None,
            "parser_proposal": None,
            "proposal_hash": None,
            "proposal_validation": None,
            "parser_execution_authorized": False,
            "current_node": (
                "generate_parser_proposal"
            ),
            "workflow_status": "FAILED",
            "progress_percent": 60,
            "error_code": (
                "UNEXPECTED_PROPOSAL_ERROR"
            ),
            "error_message": error_message,
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "generate_parser_proposal"
                ),
                status="FAILED",
                public_message=(
                    "Unexpected parser-proposal "
                    "generation failure"
                ),
                guardrail_name=(
                    "UNEXPECTED_PROPOSAL_ERROR"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=60,
            )

            database.commit()

        return node_output_state
