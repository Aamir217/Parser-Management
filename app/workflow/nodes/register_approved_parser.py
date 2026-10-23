from typing import Any

from app.core.database import SessionLocal
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.parser_registry import (
    register_bootstrap_approved_parser,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def register_approved_parser_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    node_input_state = {
        "run_id": state["run_id"],
        "proposal_id": (
            state["proposal_id"]
        ),
        "proposal_status": (
            state["proposal_status"]
        ),
        "review_decision": (
            state["review_decision"]
        ),
        "reviewer_id": (
            state["reviewer_id"]
        ),
        "proposal_hash": (
            state["proposal_hash"]
        ),
        "reviewed_proposal_hash": (
            state["reviewed_proposal_hash"]
        ),
        "schema_fingerprint": (
            state["schema_fingerprint"]
        ),
        "fingerprint_version": (
            state["fingerprint_version"]
        ),
    }

    try:
        if (
            state.get(
                "review_decision"
            )
            != "APPROVE"
        ):
            raise ValueError(
                "Parser registration requires "
                "an APPROVE decision."
            )

        if (
            state.get(
                "proposal_status"
            )
            != "APPROVED"
        ):
            raise ValueError(
                "Parser proposal is not approved."
            )

        if (
            state.get(
                "proposal_hash"
            )
            != state.get(
                "reviewed_proposal_hash"
            )
        ):
            raise ValueError(
                "Approved proposal hash mismatch."
            )

        proposal = state.get(
            "parser_proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            raise ValueError(
                "Approved parser proposal "
                "is unavailable."
            )

        parser_spec = proposal.get(
            "parser_spec"
        )

        parser_name = proposal.get(
            "parser_name_suggestion",
            (
                f"{state['filename']} "
                "Parser"
            ),
        )

        with SessionLocal() as database:
            registration = (
                register_bootstrap_approved_parser(
                    database=database,
                    parser_name=parser_name,
                    description=(
                        "Parser registered after "
                        "human approval"
                    ),
                    schema_fingerprint=state[
                        "schema_fingerprint"
                    ],
                    fingerprint_version=state[
                        "fingerprint_version"
                    ],
                    canonical_schema_json=state[
                        "canonical_schema_json"
                    ],
                    parser_spec=parser_spec,
                    created_by=state[
                        "reviewer_id"
                    ],
                    approval_owner=state[
                        "reviewer_id"
                    ],
                )
            )

            node_output_state = {
                "registered_parser_id": (
                    registration["parser_id"]
                ),
                "registered_parser_name": (
                    registration["parser_name"]
                ),
                "registered_parser_version_id": (
                    registration[
                        "parser_version_id"
                    ]
                ),
                "registered_parser_version_number": (
                    registration[
                        "version_number"
                    ]
                ),
                "matched_parser_id": (
                    registration["parser_id"]
                ),
                "matched_parser_name": (
                    registration["parser_name"]
                ),
                "matched_parser_version_id": (
                    registration[
                        "parser_version_id"
                    ]
                ),
                "matched_parser_version_number": (
                    registration[
                        "version_number"
                    ]
                ),
                "matched_parser_spec": (
                    parser_spec
                ),
                "matched_parser_approval_status": (
                    "APPROVED"
                ),
                "matched_parser_status": (
                    "ACTIVE"
                ),
                "parser_match_found": True,
                "parser_execution_authorized": True,
                "current_node": (
                    "register_approved_parser"
                ),
                "workflow_status": (
                    "PARSER_REGISTERED"
                ),
                "progress_percent": 75,
                "error_code": None,
                "error_message": None,
            }

            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "register_approved_parser"
                ),
                status="PASSED",
                public_message=(
                    "Human-approved parser was "
                    "registered as an active, "
                    "approved parser version"
                ),
                guardrail_name=(
                    "APPROVED_PROPOSAL_HASH_REQUIRED"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=75,
            )

            database.commit()

        return node_output_state

    except Exception as exception:
        node_output_state = {
            "parser_match_found": False,
            "parser_execution_authorized": False,
            "current_node": (
                "register_approved_parser"
            ),
            "workflow_status": "BLOCKED",
            "progress_percent": 75,
            "error_code": (
                "PARSER_REGISTRATION_BLOCKED"
            ),
            "error_message": str(exception),
        }

        with SessionLocal() as database:
            record_node_execution(
                database=database,
                run_id=state["run_id"],
                node_name=(
                    "register_approved_parser"
                ),
                status="BLOCKED",
                public_message=str(exception),
                guardrail_name=(
                    "PARSER_REGISTRATION_BLOCKED"
                ),
                input_state=node_input_state,
                output_state=node_output_state,
                progress_percent=75,
            )

            database.commit()

        return node_output_state
