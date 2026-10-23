import json

from fastapi import (
    APIRouter,
    HTTPException,
)
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.database import (
    NodeExecution,
    WorkflowRun,
)
from app.models.parser_proposal import (
    ParserProposal,
)
from app.workflow.graph import (
    inspection_graph,
)


router = APIRouter(
    prefix="/v1/reviews",
    tags=["Human Review"],
)


class ReviewRequest(BaseModel):
    decision: str

    reviewer_id: str = Field(
        min_length=1,
        max_length=255,
    )

    comments: str = Field(
        default="",
        max_length=2000,
    )

    proposal_hash: str = Field(
        min_length=64,
        max_length=64,
    )


def serialize_execution(
    execution: NodeExecution,
) -> dict:
    return {
        "id": execution.id,
        "sequence_number": (
            execution.sequence_number
        ),
        "node_name": execution.node_name,
        "status": execution.status,
        "public_message": (
            execution.public_message
        ),
        "guardrail_name": (
            execution.guardrail_name
        ),
        "input_state": json.loads(
            execution.input_state_json
        ),
        "output_state": json.loads(
            execution.output_state_json
        ),
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
    }


def get_executions(
    run_id: str,
) -> list[dict]:
    with SessionLocal() as database:
        executions = list(
            database.scalars(
                select(NodeExecution)
                .where(
                    NodeExecution.run_id
                    == run_id
                )
                .order_by(
                    NodeExecution.sequence_number
                )
            ).all()
        )

        return [
            serialize_execution(execution)
            for execution in executions
        ]


@router.post("/{run_id}")
def submit_review(
    run_id: str,
    request: ReviewRequest,
) -> dict:
    decision = (
        request.decision
        .strip()
        .upper()
    )

    if decision not in {
        "APPROVE",
        "REJECT",
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Decision must be "
                    "APPROVE or REJECT."
                ),
            },
        )

    graph_config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    try:
        graph_snapshot = (
            inspection_graph.get_state(
                graph_config
            )
        )
    except Exception as exception:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "No resumable LangGraph "
                    "checkpoint was found."
                ),
                "run_id": run_id,
                "technical_detail": str(
                    exception
                ),
            },
        ) from exception

    graph_is_waiting = bool(
        graph_snapshot.next
    )

    with SessionLocal() as database:
        workflow_run = database.get(
            WorkflowRun,
            run_id,
        )

        if workflow_run is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": (
                        "Workflow run not found."
                    ),
                    "run_id": run_id,
                },
            )

        proposal = database.scalar(
            select(ParserProposal).where(
                ParserProposal.run_id
                == run_id
            )
        )

        if proposal is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": (
                        "Pending parser proposal "
                        "was not found."
                    ),
                    "run_id": run_id,
                },
            )

        if not graph_is_waiting:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "LangGraph is not paused "
                        "at an interrupt."
                    ),
                    "database_status": (
                        workflow_run.status
                    ),
                    "graph_next_nodes": list(
                        graph_snapshot.next
                    ),
                },
            )

        if (
            workflow_run.status
            != "WAITING_FOR_HUMAN_REVIEW"
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Database workflow status "
                        "is not waiting for review."
                    ),
                    "database_status": (
                        workflow_run.status
                    ),
                    "expected_status": (
                        "WAITING_FOR_HUMAN_REVIEW"
                    ),
                },
            )

        if (
            proposal.proposal_status
            != "PENDING_REVIEW"
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Proposal is no longer "
                        "pending review."
                    ),
                    "proposal_status": (
                        proposal.proposal_status
                    ),
                },
            )

        if (
            proposal.proposal_hash
            != request.proposal_hash
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Proposal hash mismatch."
                    ),
                    "submitted_hash": (
                        request.proposal_hash
                    ),
                    "expected_hash": (
                        proposal.proposal_hash
                    ),
                },
            )

    resume_value = {
        "decision": decision,
        "reviewer_id": (
            request.reviewer_id.strip()
        ),
        "comments": (
            request.comments.strip()
        ),
        "proposal_hash": (
            request.proposal_hash
        ),
    }

    try:
        graph_result = inspection_graph.invoke(
            Command(
                resume=resume_value
            ),
            config=graph_config,
        )

    except Exception as exception:
        with SessionLocal() as database:
            workflow_run = database.get(
                WorkflowRun,
                run_id,
            )

            if workflow_run is not None:
                workflow_run.status = "FAILED"
                workflow_run.current_node = (
                    "human_review"
                )
                workflow_run.error_message = str(
                    exception
                )

                database.commit()

        raise HTTPException(
            status_code=422,
            detail={
                "status": "FAILED",
                "run_id": run_id,
                "message": str(exception),
            },
        ) from exception

    resumed_snapshot = (
        inspection_graph.get_state(
            graph_config
        )
    )

    if resumed_snapshot.next:
        final_status = (
            "WAITING_FOR_HUMAN_REVIEW"
        )
        final_node = (
            str(resumed_snapshot.next[0])
        )
        final_progress = 65

    else:
        final_status = graph_result.get(
            "workflow_status",
            (
                "PROPOSAL_REJECTED"
                if decision == "REJECT"
                else "FAILED"
            ),
        )

        final_node = graph_result.get(
            "current_node",
            "human_review",
        )

        final_progress = graph_result.get(
            "progress_percent",
            70,
        )

    with SessionLocal() as database:
        workflow_run = database.get(
            WorkflowRun,
            run_id,
        )

        workflow_run.status = final_status
        workflow_run.current_node = final_node
        workflow_run.progress_percent = (
            final_progress
        )
        workflow_run.error_message = (
            graph_result.get(
                "error_message"
            )
        )

        database.commit()
        database.refresh(workflow_run)

    return {
        "run_id": run_id,
        "decision": decision,
        "status": final_status,
        "current_node": final_node,
        "progress_percent": (
            final_progress
        ),
        "proposal_status": (
            graph_result.get(
                "proposal_status"
            )
        ),
        "registered_parser_id": (
            graph_result.get(
                "registered_parser_id"
            )
        ),
        "registered_parser_name": (
            graph_result.get(
                "registered_parser_name"
            )
        ),
        "registered_parser_version_id": (
            graph_result.get(
                "registered_parser_version_id"
            )
        ),
        "registered_parser_version_number": (
            graph_result.get(
                "registered_parser_version_number"
            )
        ),
        "parsed_records": (
            graph_result.get(
                "parsed_records"
            )
        ),
        "parsed_row_count": (
            graph_result.get(
                "parsed_row_count"
            )
        ),
        "validation_status": (
            graph_result.get(
                "validation_status"
            )
        ),
        "validation_summary": (
            graph_result.get(
                "validation_summary"
            )
        ),
        "validation_issues": (
            graph_result.get(
                "validation_issues"
            )
        ),
        "validation_metrics": (
            graph_result.get(
                "validation_metrics"
            )
        ),
        "duplicate_record_count": (
            graph_result.get(
                "duplicate_record_count"
            )
        ),
        "missing_required_value_count": (
            graph_result.get(
                "missing_required_value_count"
            )
        ),
        "invalid_value_count": (
            graph_result.get(
                "invalid_value_count"
            )
        ),
        "final_output_filename": (
            graph_result.get(
                "final_output_filename"
            )
        ),
        "final_output_size_bytes": (
            graph_result.get(
                "final_output_size_bytes"
            )
        ),
        "final_output_row_count": (
            graph_result.get(
                "final_output_row_count"
            )
        ),
        "final_output_column_count": (
            graph_result.get(
                "final_output_column_count"
            )
        ),
        "final_output_checksum_sha256": (
            graph_result.get(
                "final_output_checksum_sha256"
            )
        ),
        "final_output_available": (
            graph_result.get(
                "final_output_available"
            )
        ),
        "error_code": (
            graph_result.get(
                "error_code"
            )
        ),
        "error_message": (
            graph_result.get(
                "error_message"
            )
        ),
        "node_executions": (
            get_executions(run_id)
        ),
    }
