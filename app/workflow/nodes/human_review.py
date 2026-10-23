from typing import Any

from langgraph.types import interrupt
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.database import (
    NodeExecution,
)
from app.models.parser_proposal import (
    ParserProposal,
)
from app.services.node_execution_service import (
    record_node_execution,
)
from app.workflow.state import (
    ParserWorkflowState,
)


ALLOWED_REVIEW_DECISIONS = {
    "APPROVE",
    "REJECT",
}


def waiting_event_exists(
    run_id: str,
) -> bool:
    with SessionLocal() as database:
        statement = (
            select(NodeExecution.id)
            .where(
                NodeExecution.run_id == run_id,
                NodeExecution.node_name
                == "human_review",
                NodeExecution.status
                == "WAITING",
            )
            .limit(1)
        )

        return (
            database.scalar(statement)
            is not None
        )


def record_waiting_event(
    state: ParserWorkflowState,
) -> None:
    if waiting_event_exists(
        state["run_id"]
    ):
        return

    waiting_output = {
        "proposal_id": (
            state["proposal_id"]
        ),
        "proposal_status": (
            "PENDING_REVIEW"
        ),
        "proposal_hash": (
            state["proposal_hash"]
        ),
        "allowed_decisions": [
            "APPROVE",
            "REJECT",
        ],
        "parser_execution_authorized": False,
        "message": (
            "Workflow is paused. No parser "
            "is currently executing."
        ),
    }

    with SessionLocal() as database:
        record_node_execution(
            database=database,
            run_id=state["run_id"],
            node_name="human_review",
            status="WAITING",
            public_message=(
                "Workflow paused for human review. "
                "No parser is executing."
            ),
            guardrail_name=(
                "HUMAN_APPROVAL_REQUIRED"
            ),
            input_state={
                "run_id": state["run_id"],
                "file_id": state["file_id"],
                "proposal_id": (
                    state["proposal_id"]
                ),
                "proposal_status": (
                    state["proposal_status"]
                ),
                "proposal_hash": (
                    state["proposal_hash"]
                ),
                "parser_proposal": (
                    state["parser_proposal"]
                ),
            },
            output_state=waiting_output,
            progress_percent=65,
        )

        database.commit()


def validate_review_response(
    response: Any,
) -> dict[str, str]:
    if not isinstance(response, dict):
        raise ValueError(
            "Human-review response must "
            "be a dictionary."
        )

    decision = str(
        response.get(
            "decision",
            "",
        )
    ).strip().upper()

    reviewer_id = str(
        response.get(
            "reviewer_id",
            "",
        )
    ).strip()

    comments = str(
        response.get(
            "comments",
            "",
        )
    ).strip()

    reviewed_proposal_hash = str(
        response.get(
            "proposal_hash",
            "",
        )
    ).strip()

    if decision not in (
        ALLOWED_REVIEW_DECISIONS
    ):
        raise ValueError(
            "Review decision must be "
            "APPROVE or REJECT."
        )

    if not reviewer_id:
        raise ValueError(
            "Reviewer ID is required."
        )

    if not reviewed_proposal_hash:
        raise ValueError(
            "Reviewed proposal hash is required."
        )

    return {
        "decision": decision,
        "reviewer_id": reviewer_id,
        "comments": comments,
        "proposal_hash": (
            reviewed_proposal_hash
        ),
    }


def human_review_node(
    state: ParserWorkflowState,
) -> dict[str, Any]:
    """
    Pause execution until the frontend submits
    APPROVE or REJECT.

    This node is idempotent before interrupt because
    a resumed interrupt node starts from its beginning.
    """

    record_waiting_event(state)

    review_response = interrupt(
        {
            "run_id": state["run_id"],
            "file_id": state["file_id"],
            "proposal_id": (
                state["proposal_id"]
            ),
            "proposal_hash": (
                state["proposal_hash"]
            ),
            "proposal": (
                state["parser_proposal"]
            ),
            "allowed_decisions": [
                "APPROVE",
                "REJECT",
            ],
            "message": (
                "Review the parser proposal. "
                "No parser will execute until "
                "the proposal is approved."
            ),
        }
    )

    validated_response = (
        validate_review_response(
            review_response
        )
    )

    if (
        validated_response["proposal_hash"]
        != state["proposal_hash"]
    ):
        raise ValueError(
            "The reviewed proposal hash does "
            "not match the pending proposal."
        )

    decision = validated_response[
        "decision"
    ]

    workflow_status = (
        "PROPOSAL_APPROVED"
        if decision == "APPROVE"
        else "PROPOSAL_REJECTED"
    )

    proposal_status = (
        "APPROVED"
        if decision == "APPROVE"
        else "REJECTED"
    )

    with SessionLocal() as database:
        proposal_record = database.get(
            ParserProposal,
            state["proposal_id"],
        )

        if proposal_record is None:
            raise ValueError(
                "Pending parser proposal "
                "was not found."
            )

        if (
            proposal_record.proposal_hash
            != state["proposal_hash"]
        ):
            raise ValueError(
                "Stored proposal hash does not "
                "match graph state."
            )

        if (
            proposal_record.proposal_status
            != "PENDING_REVIEW"
        ):
            raise ValueError(
                "Proposal is no longer pending review."
            )

        proposal_record.proposal_status = (
            proposal_status
        )

        node_output_state = {
            "review_decision": decision,
            "reviewer_id": (
                validated_response[
                    "reviewer_id"
                ]
            ),
            "reviewer_comments": (
                validated_response[
                    "comments"
                ]
            ),
            "reviewed_proposal_hash": (
                validated_response[
                    "proposal_hash"
                ]
            ),
            "proposal_status": (
                proposal_status
            ),
            "parser_execution_authorized": (
                False
            ),
            "current_node": "human_review",
            "workflow_status": (
                workflow_status
            ),
            "progress_percent": 70,
            "error_code": None,
            "error_message": None,
        }

        record_node_execution(
            database=database,
            run_id=state["run_id"],
            node_name="human_review",
            status="PASSED",
            public_message=(
                f"Human reviewer selected "
                f"{decision}"
            ),
            guardrail_name=(
                "ATTRIBUTABLE_HUMAN_DECISION"
            ),
            input_state={
                "proposal_id": (
                    state["proposal_id"]
                ),
                "proposal_hash": (
                    state["proposal_hash"]
                ),
                "review_response": (
                    validated_response
                ),
            },
            output_state=node_output_state,
            progress_percent=70,
        )

        database.commit()

    return node_output_state
