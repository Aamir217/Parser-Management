import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.parser_proposal import (
    ParserProposal,
)
from app.services.parser_registry import (
    ParserRegistryError,
    validate_parser_specification,
)


class ParserProposalError(ValueError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.guardrail_name = guardrail_name


def choose_transformation(
    *,
    column_name: str,
    inferred_type: str,
) -> str:
    """
    Select a deterministic transformation.

    This function does not use an LLM.
    """

    normalized_name = column_name.lower()

    if inferred_type in {
        "integer",
        "decimal",
    }:
        return "parse_decimal"

    if inferred_type in {
        "date",
        "datetime",
    }:
        return "parse_date"

    if (
        normalized_name.endswith("_date")
        or normalized_name == "date"
    ):
        return "parse_date"

    if normalized_name in {
        "currency",
        "currency_code",
        "status",
        "country_code",
    }:
        return "upper"

    return "trim"


def select_source_sheet(
    workbook_metadata: dict[str, Any],
) -> dict[str, Any]:
    sheets = workbook_metadata.get(
        "sheets"
    )

    if (
        not isinstance(sheets, list)
        or not sheets
    ):
        raise ParserProposalError(
            message=(
                "Inspected workbook sheets "
                "are required."
            ),
            guardrail_name=(
                "INSPECTED_SHEETS_REQUIRED"
            ),
        )

    visible_sheets = [
        sheet        for sheet in sheets
        if not sheet.get(
            "is_hidden",
            False,
        )
    ]

    if visible_sheets:
        return visible_sheets[0]

    return sheets[0]


def build_type_lookup(
    sheet_metadata: dict[str, Any],
) -> dict[str, str]:
    type_lookup: dict[str, str] = {}

    for profile in sheet_metadata.get(
        "column_profiles",
        [],
    ):
        if not isinstance(profile, dict):
            continue

        column_name = profile.get(
            "normalized_name"
        )

        if not column_name:
            continue

        type_lookup[column_name] = (
            profile.get(
                "inferred_type",
                "unknown",
            )
        )

    return type_lookup


def generate_deterministic_proposal(
    *,
    workbook_metadata: dict[str, Any],
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    """
    Generate a safe declarative parser proposal.

    This proposal cannot execute before approval.
    """

    if (
        not isinstance(
            schema_fingerprint,
            str,
        )
        or len(schema_fingerprint) != 64
    ):
        raise ParserProposalError(
            message=(
                "A valid schema fingerprint "
                "is required."
            ),
            guardrail_name=(
                "VALID_SCHEMA_FINGERPRINT_REQUIRED"
            ),
        )

    if not fingerprint_version:
        raise ParserProposalError(
            message=(
                "Fingerprint version is required."
            ),
            guardrail_name=(
                "FINGERPRINT_VERSION_REQUIRED"
            ),
        )

    source_sheet = select_source_sheet(
        workbook_metadata
    )

    source_sheet_name = source_sheet.get(
        "name"
    )

    header_row = source_sheet.get(
        "header_row"
    )

    normalized_headers = source_sheet.get(
        "normalized_headers"
    )

    if (
        not isinstance(source_sheet_name, str)
        or not source_sheet_name
    ):
        raise ParserProposalError(
            message=(
                "A source sheet name is required."
            ),
            guardrail_name=(
                "SOURCE_SHEET_REQUIRED"
            ),
        )

    if (
        not isinstance(header_row, int)
        or header_row < 1
    ):
        raise ParserProposalError(
            message=(
                "A valid header row is required."
            ),
            guardrail_name=(
                "VALID_HEADER_ROW_REQUIRED"
            ),
        )

    if (
        not isinstance(
            normalized_headers,
            list,
        )
        or not normalized_headers
    ):
        raise ParserProposalError(
            message=(
                "Normalized headers are required."
            ),
            guardrail_name=(
                "NORMALIZED_HEADERS_REQUIRED"
            ),
        )

    type_lookup = build_type_lookup(
        source_sheet
    )

    mappings: list[dict[str, Any]] = []

    for column_name in normalized_headers:
        inferred_type = type_lookup.get(
            column_name,
            "unknown",
        )

        mappings.append(
            {
                "source": column_name,
                "target": column_name,
                "transform": (
                    choose_transformation(
                        column_name=column_name,
                        inferred_type=(
                            inferred_type
                        ),
                    )
                ),
                "required": False,
            }
        )

    parser_spec = {
        "source_sheet": source_sheet_name,
        "header_row": header_row,
        "mappings": mappings,
        "assumptions": [
            (
                "The detected source sheet "
                "contains the business data."
            ),
            (
                "Normalized column names are used "
                "as proposed target-field names."
            ),
            (
                "All proposed fields are optional "
                "until a human reviewer confirms "
                "required-field rules."
            ),
        ],
        "description": (
            "Deterministically generated parser "
            "proposal for human review."
        ),
    }

    try:
        validate_parser_specification(
            parser_spec
        )

    except ParserRegistryError as exception:
        raise ParserProposalError(
            message=exception.message,
            guardrail_name=(
                exception.guardrail_name
            ),
        ) from exception

    proposal = {
        "proposal_version": "1.0",
        "proposal_source": "DETERMINISTIC",
        "schema_fingerprint": (
            schema_fingerprint
        ),
        "fingerprint_version": (
            fingerprint_version
        ),
        "parser_name_suggestion": (
            f"{source_sheet_name} Parser"
        ),
        "parser_spec": parser_spec,
        "review_requirements": [
            (
                "Confirm the source sheet."
            ),
            (
                "Confirm the detected header row."
            ),
            (
                "Confirm source-to-target mappings."
            ),
            (
                "Confirm required and optional fields."
            ),
            (
                "Confirm proposed transformations."
            ),
        ],
        "execution_allowed": False,
        "approval_required": True,
    }

    return proposal


def serialize_proposal(
    proposal: dict[str, Any],
) -> str:
    return json.dumps(
        proposal,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def calculate_proposal_hash(
    proposal_json: str,
) -> str:
    return hashlib.sha256(
        proposal_json.encode("utf-8")
    ).hexdigest()


def validate_generated_proposal(
    proposal: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise ParserProposalError(
            message=(
                "Generated proposal must be "
                "a dictionary."
            ),
            guardrail_name=(
                "STRUCTURED_PROPOSAL_REQUIRED"
            ),
        )

    if proposal.get(
        "execution_allowed"
    ) is not False:
        raise ParserProposalError(
            message=(
                "An unapproved proposal cannot "
                "authorize execution."
            ),
            guardrail_name=(
                "UNAPPROVED_EXECUTION_BLOCKED"
            ),
        )

    if proposal.get(
        "approval_required"
    ) is not True:
        raise ParserProposalError(
            message=(
                "Human approval must be required."
            ),
            guardrail_name=(
                "HUMAN_APPROVAL_REQUIRED"
            ),
        )

    parser_spec = proposal.get(
        "parser_spec"
    )

    try:
        validate_parser_specification(
            parser_spec
        )

    except ParserRegistryError as exception:
        raise ParserProposalError(
            message=exception.message,
            guardrail_name=(
                exception.guardrail_name
            ),
        ) from exception

    mappings = parser_spec["mappings"]

    invalid_transformations = [
        mapping["transform"]
        for mapping in mappings
        if mapping["transform"]
        in {
            "eval",
            "exec",
            "python",
            "shell",
            "sql",
            "http",
        }
    ]

    if invalid_transformations:
        raise ParserProposalError(
            message=(
                "Proposal contains prohibited "
                "execution operations."
            ),
            guardrail_name=(
                "EXECUTABLE_CODE_PROHIBITED"
            ),
        )

    return {
        "status": "PASSED",
        "structured_output": True,
        "declarative_only": True,
        "executable_code_present": False,
        "human_approval_required": True,
        "execution_allowed": False,
        "mapping_count": len(mappings),
    }


def save_pending_proposal(
    database: Session,
    *,
    run_id: str,
    file_id: str,
    schema_fingerprint: str,
    fingerprint_version: str,
    proposal: dict[str, Any],
    validation_result: dict[str, Any],
) -> ParserProposal:
    existing = database.scalar(
        select(ParserProposal).where(
            ParserProposal.run_id == run_id
        )
    )

    proposal_json = serialize_proposal(
        proposal
    )

    proposal_hash = (
        calculate_proposal_hash(
            proposal_json
        )
    )

    if existing is not None:
        existing.proposal_status = (
            "PENDING_REVIEW"
        )
        existing.proposal_source = str(
            proposal.get(
                "proposal_source",
                "DETERMINISTIC",
            )
        )
        existing.proposal_json = (
            proposal_json
        )
        existing.proposal_hash = (
            proposal_hash
        )
        existing.validation_result_json = (
            json.dumps(
                validation_result,
                sort_keys=True,
            )
        )

        database.flush()

        return existing

    proposal_record = ParserProposal(
        id=str(uuid4()),
        run_id=run_id,
        file_id=file_id,
        schema_fingerprint=(
            schema_fingerprint
        ),
        fingerprint_version=(
            fingerprint_version
        ),
        proposal_status=(
            "PENDING_REVIEW"
        ),
        proposal_source=str(
            proposal.get(
                "proposal_source",
                "DETERMINISTIC",
            )
        ),
        proposal_json=proposal_json,
        proposal_hash=proposal_hash,
        validation_result_json=json.dumps(
            validation_result,
            sort_keys=True,
        ),
    )

    database.add(proposal_record)
    database.flush()

    return proposal_record
