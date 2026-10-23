import json
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.database import (
    NodeExecution,
    UploadedFile,
    WorkflowRun,
)
from app.services.node_execution_service import (
    record_node_execution,
)
from app.services.upload_guardrails import (
    UploadGuardrailError,
    validate_upload,
)
from app.workflow.graph import (
    inspection_graph,
)


router = APIRouter(
    prefix="/v1/uploads",
    tags=["Uploads"],
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


def get_run_executions(
    database,
    run_id: str,
) -> list[NodeExecution]:
    statement = (
        select(NodeExecution)
        .where(
            NodeExecution.run_id == run_id
        )
        .order_by(
            NodeExecution.sequence_number
        )
    )

    return list(
        database.scalars(
            statement
        ).all()
    )


def remove_stored_file_if_present(
    stored_path: Path | None,
) -> None:
    if (
        stored_path is not None
        and stored_path.exists()
        and stored_path.is_file()
    ):
        stored_path.unlink()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def upload_excel(
    uploaded_file: UploadFile = File(...),
) -> dict:
    run_id = str(uuid4())
    file_id = str(uuid4())

    original_filename = (
        uploaded_file.filename
        or "unnamed-upload"
    )

    content = await uploaded_file.read()

    validation_input_state = {
        "run_id": run_id,
        "file_id": file_id,
        "original_filename": (
            original_filename
        ),
        "content_type": (
            uploaded_file.content_type
        ),
        "configured_maximum_size_mb": (
            settings.max_file_size_mb
        ),
        "allowed_extensions": [
            ".xlsx",
        ],
    }

    stored_path: Path | None = None

    with SessionLocal() as database:
        workflow_run = WorkflowRun(
            id=run_id,
            file_id=file_id,
            filename=original_filename,
            status="RUNNING",
            current_node="validate_upload",
            progress_percent=5,
            error_message=None,
        )

        database.add(workflow_run)
        database.commit()

        try:
            validation_result = validate_upload(
                filename=original_filename,
                content=content,
            )

            validation_output_state = {
                "file_id": file_id,
                "sanitized_filename": (
                    validation_result[
                        "sanitized_filename"
                    ]
                ),
                "extension": (
                    validation_result["extension"]
                ),
                "size_bytes": (
                    validation_result["size_bytes"]
                ),
                "checksum_sha256": (
                    validation_result[
                        "checksum_sha256"
                    ]
                ),
                "guardrails": (
                    validation_result["guardrails"]
                ),
            }

            record_node_execution(
                database=database,
                run_id=run_id,
                node_name="validate_upload",
                status="PASSED",
                public_message=(
                    "File upload guardrails passed"
                ),
                guardrail_name=(
                    "DETERMINISTIC_UPLOAD_GUARDRAILS"
                ),
                input_state=(
                    validation_input_state
                ),
                output_state=(
                    validation_output_state
                ),
                progress_percent=10,
            )

            database.commit()

            stored_filename = (
                f"{file_id}.xlsx"
            )

            stored_path = (
                Path(
                    settings.upload_directory
                )
                / stored_filename
            )

            stored_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if stored_path.exists():
                raise UploadGuardrailError(
                    message=(
                        "Generated immutable storage "
                        "path already exists."
                    ),
                    guardrail_name=(
                        "IMMUTABLE_STORAGE_PATH"
                    ),
                )

            storage_input_state = {
                "run_id": run_id,
                "file_id": file_id,
                "checksum_sha256": (
                    validation_result[
                        "checksum_sha256"
                    ]
                ),
                "size_bytes": (
                    validation_result["size_bytes"]
                ),
                "storage_identity": (
                    stored_filename
                ),
            }

            with stored_path.open(
                "xb"
            ) as output_file:
                output_file.write(content)

            database.add(
                UploadedFile(
                    id=file_id,
                    run_id=run_id,
                    original_filename=(
                        original_filename
                    ),
                    stored_filename=(
                        stored_filename
                    ),
                    stored_path=str(
                        stored_path
                    ),
                    extension=(
                        validation_result[
                            "extension"
                        ]
                    ),
                    content_type=(
                        uploaded_file.content_type
                    ),
                    size_bytes=(
                        validation_result[
                            "size_bytes"
                        ]
                    ),
                    checksum_sha256=(
                        validation_result[
                            "checksum_sha256"
                        ]
                    ),
                    validation_status="PASSED",
                )
            )

            storage_output_state = {
                "file_id": file_id,
                "stored_filename": (
                    stored_filename
                ),
                "original_filename_preserved": (
                    True
                ),
                "immutable_write_mode": True,
                "stored_size_bytes": (
                    stored_path.stat().st_size
                ),
            }

            record_node_execution(
                database=database,
                run_id=run_id,
                node_name="store_original",
                status="PASSED",
                public_message=(
                    "Original workbook stored "
                    "with an immutable file identity"
                ),
                guardrail_name=(
                    "IMMUTABLE_ORIGINAL_FILE"
                ),
                input_state=(
                    storage_input_state
                ),
                output_state=(
                    storage_output_state
                ),
                progress_percent=15,
            )

            workflow_run.status = (
                "UPLOAD_COMPLETED"
            )
            workflow_run.current_node = (
                "store_original"
            )
            workflow_run.progress_percent = 15
            workflow_run.error_message = None

            database.commit()

        except UploadGuardrailError as exception:
            database.rollback()

            workflow_run = database.get(
                WorkflowRun,
                run_id,
            )

            record_node_execution(
                database=database,
                run_id=run_id,
                node_name="validate_upload",
                status="BLOCKED",
                public_message=(
                    exception.message
                ),
                guardrail_name=(
                    exception.guardrail_name
                ),
                input_state=(
                    validation_input_state
                ),
                output_state={
                    "file_id": file_id,
                    "error": exception.message,
                    "guardrail_name": (
                        exception.guardrail_name
                    ),
                    "file_stored": False,
                },
                progress_percent=10,
            )

            if workflow_run is not None:
                workflow_run.status = "BLOCKED"
                workflow_run.current_node = (
                    "validate_upload"
                )
                workflow_run.progress_percent = 10
                workflow_run.error_message = (
                    exception.message
                )

            database.commit()

            remove_stored_file_if_present(
                stored_path
            )

            raise HTTPException(
                status_code=400,
                detail={
                    "run_id": run_id,
                    "file_id": file_id,
                    "status": "BLOCKED",
                    "current_node": (
                        "validate_upload"
                    ),
                    "progress_percent": 10,
                    "guardrail_name": (
                        exception.guardrail_name
                    ),
                    "message": exception.message,
                },
            ) from exception

        except Exception as exception:
            database.rollback()

            remove_stored_file_if_present(
                stored_path
            )

            workflow_run = database.get(
                WorkflowRun,
                run_id,
            )

            if workflow_run is not None:
                workflow_run.status = "FAILED"
                workflow_run.current_node = (
                    "upload_failure"
                )
                workflow_run.progress_percent = 10
                workflow_run.error_message = str(
                    exception
                )
                database.commit()

            raise HTTPException(
                status_code=500,
                detail={
                    "run_id": run_id,
                    "file_id": file_id,
                    "status": "FAILED",
                    "message": str(exception),
                },
            ) from exception

    graph_input_state = {
        "run_id": run_id,
        "file_id": file_id,
        "filename": original_filename,
        "stored_path": str(stored_path),
        "checksum_sha256": (
            validation_result[
                "checksum_sha256"
            ]
        ),
        "size_bytes": (
            validation_result["size_bytes"]
        ),
        "current_node": "store_original",
        "workflow_status": (
            "UPLOAD_COMPLETED"
        ),
        "progress_percent": 15,
        "error_code": None,
        "error_message": None,
    }

    graph_config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    graph_result = inspection_graph.invoke(
        graph_input_state,
        config=graph_config,
    )

    # Read the actual LangGraph checkpoint.
    # When interrupt() pauses execution, snapshot.next
    # contains the node waiting to be resumed.
    graph_snapshot = inspection_graph.get_state(
        graph_config
    )

    graph_is_interrupted = bool(
        graph_snapshot.next
    )

    print(
        "[LANGGRAPH CHECKPOINT]",
        {
            "run_id": run_id,
            "next_nodes": list(
                graph_snapshot.next
            ),
            "is_interrupted": (
                graph_is_interrupted
            ),
            "state_status": (
                graph_snapshot.values.get(
                    "workflow_status"
                )
            ),
            "state_current_node": (
                graph_snapshot.values.get(
                    "current_node"
                )
            ),
        },
        flush=True,
    )

    with SessionLocal() as database:
        workflow_run = database.get(
            WorkflowRun,
            run_id,
        )

        if workflow_run is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Workflow run was not found "
                    "after graph execution."
                ),
            )

        if graph_is_interrupted:
            final_status = (
                "WAITING_FOR_HUMAN_REVIEW"
            )

            final_node = "human_review"
            final_progress = 65
            final_error_message = None

        else:
            final_status = graph_result.get(
                "workflow_status",
                "FAILED",
            )

            final_node = graph_result.get(
                "current_node",
                "unknown",
            )

            final_progress = graph_result.get(
                "progress_percent",
                0,
            )

            final_error_message = graph_result.get(
                "error_message"
            )

        workflow_run.status = final_status
        workflow_run.current_node = final_node
        workflow_run.progress_percent = (
            final_progress
        )
        workflow_run.error_message = (
            final_error_message
        )

        database.commit()
        database.refresh(workflow_run)

        executions = get_run_executions(
            database,
            run_id,
        )

        response_body = {
            "run_id": run_id,
            "file_id": file_id,
            "original_filename": (
                original_filename
            ),
            "stored_filename": (
                stored_path.name
            ),
            "status": workflow_run.status,
            "current_node": (
                workflow_run.current_node
            ),
            "progress_percent": (
                workflow_run.progress_percent
            ),
            "size_bytes": (
                validation_result["size_bytes"]
            ),
            "checksum_sha256": (
                validation_result[
                    "checksum_sha256"
                ]
            ),
            "workbook_metadata": (
                graph_result.get(
                    "workbook_metadata"
                )
            ),
            "canonical_schema": (
                graph_result.get(
                    "canonical_schema"
                )
            ),
            "canonical_schema_json": (
                graph_result.get(
                    "canonical_schema_json"
                )
            ),
            "schema_fingerprint": (
                graph_result.get(
                    "schema_fingerprint"
                )
            ),
            "fingerprint_version": (
                graph_result.get(
                    "fingerprint_version"
                )
            ),
            "parser_match_found": (
                graph_result.get(
                    "parser_match_found"
                )
            ),
            "parser_execution_authorized": (
                graph_result.get(
                    "parser_execution_authorized"
                )
            ),
            "parser_match_policy": (
                graph_result.get(
                    "parser_match_policy"
                )
            ),
            "matched_parser_id": (
                graph_result.get(
                    "matched_parser_id"
                )
            ),
            "matched_parser_name": (
                graph_result.get(
                    "matched_parser_name"
                )
            ),
            "matched_parser_version_id": (
                graph_result.get(
                    "matched_parser_version_id"
                )
            ),
            "matched_parser_version_number": (
                graph_result.get(
                    "matched_parser_version_number"
                )
            ),
            "matched_parser_spec": (
                graph_result.get(
                    "matched_parser_spec"
                )
            ),
            "matched_parser_approval_status": (
                graph_result.get(
                    "matched_parser_approval_status"
                )
            ),
            "matched_parser_status": (
                graph_result.get(
                    "matched_parser_status"
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
            "source_row_count": (
                graph_result.get(
                    "source_row_count"
                )
            ),
            "rejected_row_count": (
                graph_result.get(
                    "rejected_row_count"
                )
            ),
            "output_truncated": (
                graph_result.get(
                    "output_truncated"
                )
            ),
            "parser_execution_summary": (
                graph_result.get(
                    "parser_execution_summary"
                )
            ),
            "proposal_id": (
                graph_result.get(
                    "proposal_id"
                )
            ),
            "proposal_status": (
                graph_result.get(
                    "proposal_status"
                )
            ),
            "proposal_source": (
                graph_result.get(
                    "proposal_source"
                )
            ),
            "parser_proposal": (
                graph_result.get(
                    "parser_proposal"
                )
            ),
            "proposal_hash": (
                graph_result.get(
                    "proposal_hash"
                )
            ),
            "proposal_validation": (
                graph_result.get(
                    "proposal_validation"
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
            "node_executions": [
                serialize_execution(
                    execution
                )
                for execution in executions
            ],
        }

        if workflow_run.status in {
            "BLOCKED",
            "FAILED",
        }:
            raise HTTPException(
                status_code=422,
                detail=response_body,
            )

        return response_body
