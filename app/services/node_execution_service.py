import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import (
    NodeExecution,
    WorkflowRun,
)


# These fields must never be exposed through
# the frontend node-inspection interface.
BLOCKED_STATE_FIELDS = {
    "stored_path",
    "file_path",
    "database_url",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "password",
    "credentials",
    "service_account_key",
}


# Limit the amount of list data shown in the frontend.
# This prevents large parsed datasets from being copied
# into the node execution history.
MAX_VISIBLE_LIST_ITEMS = 50


# Limit very long strings in node snapshots.
MAX_VISIBLE_STRING_LENGTH = 10_000


def sanitize_state_for_display(
    value: Any,
) -> Any:
    """
    Recursively prepare LangGraph node state for
    safe storage and frontend display.

    Behavior:
    - Removes sensitive/internal dictionary fields.
    - Limits displayed list sizes.
    - Limits extremely long strings.
    - Preserves normal dictionaries, lists, numbers,
      booleans, null values and short strings.
    - Converts unsupported objects to strings.

    This sanitized snapshot is for observability only.
    It is not used as the authoritative LangGraph state.
    """

    if isinstance(value, dict):
        sanitized_dictionary: dict[str, Any] = {}

        for key, item in value.items():
            normalized_key = str(key).lower()

            if normalized_key in BLOCKED_STATE_FIELDS:
                continue

            sanitized_dictionary[str(key)] = (
                sanitize_state_for_display(item)
            )

        return sanitized_dictionary

    if isinstance(value, list):
        visible_items = value[
            :MAX_VISIBLE_LIST_ITEMS
        ]

        sanitized_items = [
            sanitize_state_for_display(item)
            for item in visible_items
        ]

        if len(value) > MAX_VISIBLE_LIST_ITEMS:
            sanitized_items.append(
                {
                    "_truncated": True,
                    "_original_item_count": len(value),
                    "_displayed_item_count": (
                        MAX_VISIBLE_LIST_ITEMS
                    ),
                }
            )

        return sanitized_items

    if isinstance(value, tuple):
        return sanitize_state_for_display(
            list(value)
        )

    if isinstance(value, set):
        return sanitize_state_for_display(
            sorted(
                value,
                key=lambda item: str(item),
            )
        )

    if isinstance(value, str):
        if len(value) <= MAX_VISIBLE_STRING_LENGTH:
            return value

        return (
            value[:MAX_VISIBLE_STRING_LENGTH]
            + "...[truncated]"
        )

    if value is None:
        return None

    if isinstance(
        value,
        (
            bool,
            int,
            float,
        ),
    ):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    # Fallback for UUID, Path, Decimal, Enum
    # and other JSON-incompatible objects.
    return str(value)


def serialize_state(
    state: dict[str, Any],
) -> str:
    """
    Convert a state snapshot into JSON after applying
    frontend-safety rules.
    """

    sanitized_state = sanitize_state_for_display(
        state
    )

    return json.dumps(
        sanitized_state,
        ensure_ascii=False,
        default=str,
    )


def get_next_sequence_number(
    database: Session,
    run_id: str,
) -> int:
    """
    Return the next execution sequence number
    for a workflow run.
    """

    statement = select(
        func.coalesce(
            func.max(
                NodeExecution.sequence_number
            ),
            0,
        )
    ).where(
        NodeExecution.run_id == run_id
    )

    current_maximum = database.scalar(
        statement
    )

    return int(current_maximum or 0) + 1


def record_node_execution(
    database: Session,
    *,
    run_id: str,
    node_name: str,
    status: str,
    public_message: str,
    guardrail_name: str | None,
    input_state: dict[str, Any],
    output_state: dict[str, Any],
    progress_percent: int,
) -> NodeExecution:
    """
    Store one node execution and update its parent run.

    input_state:
        The complete state received when the node starts.

    output_state:
        Only the state update returned by that node.

    The caller controls the database transaction.
    This function uses flush(), not commit().
    """

    workflow_run = database.get(
        WorkflowRun,
        run_id,
    )

    if workflow_run is None:
        raise ValueError(
            f"Workflow run does not exist: {run_id}"
        )

    if not node_name.strip():
        raise ValueError(
            "Node name cannot be empty."
        )

    allowed_statuses = {
        "PENDING",
        "RUNNING",
        "PASSED",
        "WAITING",
        "BLOCKED",
        "FAILED",
        "COMPLETED",
    }

    if status not in allowed_statuses:
        raise ValueError(
            "Unsupported node status: "
            f"{status}. Allowed values: "
            f"{sorted(allowed_statuses)}"
        )

    if not 0 <= progress_percent <= 100:
        raise ValueError(
            "Progress percentage must be "
            "between 0 and 100."
        )

    sequence_number = get_next_sequence_number(
        database=database,
        run_id=run_id,
    )

    current_time = datetime.now(UTC)

    execution = NodeExecution(
        run_id=run_id,
        sequence_number=sequence_number,
        node_name=node_name,
        status=status,
        public_message=public_message,
        guardrail_name=guardrail_name,
        input_state_json=serialize_state(
            input_state
        ),
        output_state_json=serialize_state(
            output_state
        ),
        started_at=current_time,
        completed_at=(
            None
            if status
            in {
                "PENDING",
                "RUNNING",
                "WAITING",
            }
            else current_time
        ),
    )

    database.add(execution)

    workflow_run.current_node = node_name
    workflow_run.status = status
    workflow_run.progress_percent = (
        progress_percent
    )
    workflow_run.updated_at = current_time

    if status not in {
        "BLOCKED",
        "FAILED",
    }:
        workflow_run.error_message = None

    # flush() assigns execution.id without finalizing
    # the transaction. The API route will call commit().
    database.flush()

    return execution


def mark_node_running(
    database: Session,
    *,
    run_id: str,
    node_name: str,
    public_message: str,
    guardrail_name: str | None,
    input_state: dict[str, Any],
    progress_percent: int,
) -> NodeExecution:
    """
    Convenience function for recording a node that
    is currently running.
    """

    return record_node_execution(
        database=database,
        run_id=run_id,
        node_name=node_name,
        status="RUNNING",
        public_message=public_message,
        guardrail_name=guardrail_name,
        input_state=input_state,
        output_state={
            "message": (
                "Node execution is in progress."
            ),
        },
        progress_percent=progress_percent,
    )


def mark_node_waiting(
    database: Session,
    *,
    run_id: str,
    node_name: str,
    public_message: str,
    guardrail_name: str | None,
    input_state: dict[str, Any],
    waiting_payload: dict[str, Any],
    progress_percent: int,
) -> NodeExecution:
    """
    Convenience function for a LangGraph interrupt
    or another node waiting for external input.
    """

    return record_node_execution(
        database=database,
        run_id=run_id,
        node_name=node_name,
        status="WAITING",
        public_message=public_message,
        guardrail_name=guardrail_name,
        input_state=input_state,
        output_state=waiting_payload,
        progress_percent=progress_percent,
    )
