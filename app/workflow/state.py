from typing import Any, TypedDict


class ParserWorkflowState(
    TypedDict,
    total=False,
):
    run_id: str
    file_id: str
    filename: str
    stored_path: str

    checksum_sha256: str
    size_bytes: int

    workbook_metadata: dict[str, Any]

    canonical_schema: dict[str, Any]
    canonical_schema_json: str
    schema_fingerprint: str
    fingerprint_version: str

    parser_match_found: bool
    parser_execution_authorized: bool
    parser_match_policy: str

    matched_parser_id: str | None
    matched_parser_name: str | None
    matched_parser_version_id: str | None
    matched_parser_version_number: int | None
    matched_parser_spec: dict[str, Any] | None
    matched_parser_approval_status: str | None
    matched_parser_status: str | None

    proposal_id: str | None
    proposal_status: str | None
    proposal_source: str | None
    parser_proposal: dict[str, Any] | None
    proposal_hash: str | None
    proposal_validation: dict[str, Any] | None

    review_decision: str | None
    reviewer_id: str | None
    reviewer_comments: str | None
    reviewed_proposal_hash: str | None

    registered_parser_id: str | None
    registered_parser_name: str | None
    registered_parser_version_id: str | None
    registered_parser_version_number: int | None

    parsed_records: list[dict[str, Any]]
    parsed_row_count: int
    source_row_count: int
    rejected_row_count: int
    output_truncated: bool
    parser_execution_summary: dict[str, Any]

    validation_status: str
    validation_summary: dict[str, Any]
    validation_issues: list[dict[str, Any]]
    validation_metrics: dict[str, Any]
    duplicate_record_count: int
    missing_required_value_count: int
    invalid_value_count: int

    # Final validated XLSX file.
    final_output_path: str
    final_output_filename: str
    final_output_size_bytes: int
    final_output_row_count: int
    final_output_column_count: int
    final_output_checksum_sha256: str
    final_output_available: bool

    current_node: str
    workflow_status: str
    progress_percent: int

    error_code: str | None
    error_message: str | None
