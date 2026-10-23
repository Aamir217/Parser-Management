from datetime import datetime

from pydantic import BaseModel


class NodeExecutionResponse(BaseModel):
    id: int
    sequence_number: int
    node_name: str
    status: str
    public_message: str
    guardrail_name: str | None
    input_state: dict
    output_state: dict
    started_at: datetime
    completed_at: datetime | None


class UploadResponse(BaseModel):
    run_id: str
    file_id: str
    original_filename: str
    stored_filename: str
    status: str
    current_node: str
    progress_percent: int
    size_bytes: int
    checksum_sha256: str
    node_executions: list[NodeExecutionResponse]


class RunResponse(BaseModel):
    run_id: str
    file_id: str | None
    filename: str | None
    status: str
    current_node: str
    progress_percent: int
    error_message: str | None
    node_executions: list[NodeExecutionResponse]
