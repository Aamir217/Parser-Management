import json

from fastapi import (
    APIRouter,
    HTTPException,
)
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.database import (
    NodeExecution,
    WorkflowRun,
)


router = APIRouter(
    prefix="/v1/runs",
    tags=["Runs"],
)


def deserialize_json(
    value: str,
) -> dict:
    try:
        result = json.loads(value)

        if isinstance(result, dict):
            return result

        return {
            "value": result,
        }

    except json.JSONDecodeError:
        return {
            "error": (
                "Stored state could not be decoded"
            ),
        }


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
        "input_state": deserialize_json(
            execution.input_state_json
        ),
        "output_state": deserialize_json(
            execution.output_state_json
        ),
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
    }


@router.get("/{run_id}")
def get_run(
    run_id: str,
) -> dict:
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
                        "Workflow run not found"
                    ),
                    "run_id": run_id,
                },
            )

        query = (
            select(NodeExecution)
            .where(
                NodeExecution.run_id == run_id
            )
            .order_by(
                NodeExecution.sequence_number
            )
        )

        executions = list(
            database.scalars(query).all()
        )

        return {
            "run_id": workflow_run.id,
            "file_id": workflow_run.file_id,
            "filename": workflow_run.filename,
            "status": workflow_run.status,
            "current_node": (
                workflow_run.current_node
            ),
            "progress_percent": (
                workflow_run.progress_percent
            ),
            "error_message": (
                workflow_run.error_message
            ),
            "created_at": (
                workflow_run.created_at
            ),
            "updated_at": (
                workflow_run.updated_at
            ),
            "node_executions": [
                serialize_execution(execution)
                for execution in executions
            ],
        }


@router.get("/{run_id}/debug")
def debug_run(
    run_id: str,
) -> dict:
    from app.workflow.graph import (
        inspection_graph,
    )

    graph_config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    with SessionLocal() as database:
        workflow_run = database.get(
            WorkflowRun,
            run_id,
        )

        if workflow_run is None:
            raise HTTPException(
                status_code=404,
                detail="Workflow run not found",
            )

    try:
        snapshot = inspection_graph.get_state(
            graph_config
        )

        return {
            "run_id": run_id,
            "database_status": (
                workflow_run.status
            ),
            "database_current_node": (
                workflow_run.current_node
            ),
            "database_progress": (
                workflow_run.progress_percent
            ),
            "graph_next_nodes": list(
                snapshot.next
            ),
            "graph_is_waiting": bool(
                snapshot.next
            ),
            "graph_state_status": (
                snapshot.values.get(
                    "workflow_status"
                )
            ),
            "graph_state_current_node": (
                snapshot.values.get(
                    "current_node"
                )
            ),
            "proposal_id": (
                snapshot.values.get(
                    "proposal_id"
                )
            ),
            "proposal_status": (
                snapshot.values.get(
                    "proposal_status"
                )
            ),
        }

    except Exception as exception:
        return {
            "run_id": run_id,
            "database_status": (
                workflow_run.status
            ),
            "database_current_node": (
                workflow_run.current_node
            ),
            "database_progress": (
                workflow_run.progress_percent
            ),
            "graph_is_waiting": False,
            "graph_error": str(exception),
        }


@router.get("/{run_id}/download")
def download_validated_xlsx(
    run_id: str,
):
    from pathlib import Path

    from fastapi.responses import FileResponse

    from app.core.config import settings

    with SessionLocal() as database:
        workflow_run = database.get(
            WorkflowRun,
            run_id,
        )

        if workflow_run is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Workflow run not found."
                ),
            )

        if (
            workflow_run.status
            != "FINAL_FILE_READY"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Validated XLSX is not ready."
                ),
            )

    output_directory = Path(
        settings.output_directory
    )

    matching_files = list(
        output_directory.glob(
            f"*_validated_{run_id[:8]}.xlsx"
        )
    )

    if len(matching_files) != 1:
        raise HTTPException(
            status_code=404,
            detail=(
                "Validated XLSX output "
                "was not found."
            ),
        )

    output_path = matching_files[0]

    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type=(
            "application/vnd."
            "openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
