import hashlib
import json
from typing import Any

from app.core.config import settings


class SchemaFingerprintError(ValueError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ):
        super().__init__(message)

        self.message = message
        self.guardrail_name = guardrail_name


def validate_workbook_metadata(
    workbook_metadata: dict[str, Any],
) -> None:
    """
    Validate that the workbook-inspection output
    contains the fields required for deterministic
    fingerprint generation.
    """

    if not isinstance(
        workbook_metadata,
        dict,
    ):
        raise SchemaFingerprintError(
            message=(
                "Workbook metadata must be "
                "a dictionary."
            ),
            guardrail_name=(
                "WORKBOOK_METADATA_REQUIRED"
            ),
        )

    sheets = workbook_metadata.get("sheets")

    if not isinstance(sheets, list):
        raise SchemaFingerprintError(
            message=(
                "Workbook metadata does not "
                "contain a valid sheets list."
            ),
            guardrail_name=(
                "WORKBOOK_SHEETS_REQUIRED"
            ),
        )

    if not sheets:
        raise SchemaFingerprintError(
            message=(
                "At least one inspected sheet "
                "is required for fingerprinting."
            ),
            guardrail_name=(
                "WORKBOOK_SHEETS_REQUIRED"
            ),
        )

    for sheet_position, sheet in enumerate(
        sheets,
        start=1,
    ):
        if not isinstance(sheet, dict):
            raise SchemaFingerprintError(
                message=(
                    "Invalid sheet metadata at "
                    f"position {sheet_position}."
                ),
                guardrail_name=(
                    "VALID_SHEET_METADATA"
                ),
            )

        normalized_name = sheet.get(
            "normalized_name"
        )

        if not normalized_name:
            raise SchemaFingerprintError(
                message=(
                    "A normalized sheet name is "
                    "required at position "
                    f"{sheet_position}."
                ),
                guardrail_name=(
                    "NORMALIZED_SHEET_NAME_REQUIRED"
                ),
            )

        normalized_headers = sheet.get(
            "normalized_headers"
        )

        if not isinstance(
            normalized_headers,
            list,
        ):
            raise SchemaFingerprintError(
                message=(
                    "Normalized headers are "
                    "required for sheet "
                    f"'{normalized_name}'."
                ),
                guardrail_name=(
                    "NORMALIZED_HEADERS_REQUIRED"
                ),
            )

        if not normalized_headers:
            raise SchemaFingerprintError(
                message=(
                    "At least one normalized "
                    "header is required for sheet "
                    f"'{normalized_name}'."
                ),
                guardrail_name=(
                    "NORMALIZED_HEADERS_REQUIRED"
                ),
            )


def build_column_type_lookup(
    sheet: dict[str, Any],
) -> dict[str, str]:
    """
    Build a lookup from normalized column name
    to deterministic inferred type.
    """

    type_lookup: dict[str, str] = {}

    column_profiles = sheet.get(
        "column_profiles",
        [],
    )

    for profile in column_profiles:
        if not isinstance(profile, dict):
            continue

        column_name = profile.get(
            "normalized_name"
        )

        inferred_type = profile.get(
            "inferred_type",
            "unknown",
        )

        if column_name:
            type_lookup[str(column_name)] = str(
                inferred_type
            )

    return type_lookup


def build_canonical_schema(
    workbook_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Create the stable schema representation.

    Intentionally included:
    - fingerprint version
    - sheet order
    - normalized sheet name
    - sheet visibility
    - detected header-row position
    - column order
    - normalized column names
    - inferred column types
    - formula presence
    - merged-cell presence

    Intentionally excluded:
    - run ID
    - file ID
    - filename
    - server path
    - checksum of the complete file
    - row count
    - actual business values
    - sampled value counts
    - formula expressions
    - formula-cell coordinates
    - merged-cell coordinates
    - timestamps

    Excluding those values allows workbooks with
    the same schema but different business rows to
    produce the same schema fingerprint.
    """

    validate_workbook_metadata(
        workbook_metadata
    )

    canonical_sheets: list[
        dict[str, Any]
    ] = []

    source_sheets = workbook_metadata["sheets"]

    for default_position, sheet in enumerate(
        source_sheets,
        start=1,
    ):
        normalized_headers = list(
            sheet.get(
                "normalized_headers",
                [],
            )
        )

        type_lookup = (
            build_column_type_lookup(sheet)
        )

        canonical_columns = [
            {
                "position": column_position,
                "normalized_name": (
                    normalized_header
                ),
                "inferred_type": (
                    type_lookup.get(
                        normalized_header,
                        "unknown",
                    )
                ),
            }
            for column_position, normalized_header
            in enumerate(
                normalized_headers,
                start=1,
            )
        ]

        formula_count = int(
            sheet.get(
                "formula_count",
                0,
            )
            or 0
        )

        merged_range_count = int(
            sheet.get(
                "merged_range_count",
                0,
            )
            or 0
        )

        canonical_sheet = {
            "position": int(
                sheet.get(
                    "position",
                    default_position,
                )
            ),
            "normalized_name": str(
                sheet["normalized_name"]
            ),
            "visibility": str(
                sheet.get(
                    "visibility",
                    "visible",
                )
            ),
            "header_row": int(
                sheet.get(
                    "header_row",
                    1,
                )
            ),
            "columns": canonical_columns,
            "contains_formulas": (
                formula_count > 0
            ),
            "contains_merged_cells": (
                merged_range_count > 0
            ),
        }

        canonical_sheets.append(
            canonical_sheet
        )

    canonical_sheets.sort(
        key=lambda sheet: sheet["position"]
    )

    return {
        "fingerprint_version": (
            settings.fingerprint_version
        ),
        "sheet_count": len(
            canonical_sheets
        ),
        "sheets": canonical_sheets,
    }


def serialize_canonical_schema(
    canonical_schema: dict[str, Any],
) -> str:
    """
    Serialize using stable JSON rules.

    - sort_keys provides stable dictionary ordering
    - compact separators prevent whitespace variation
    - ensure_ascii keeps serialization consistent
    """

    return json.dumps(
        canonical_schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def calculate_schema_fingerprint(
    canonical_schema_json: str,
) -> str:
    """
    Calculate the SHA-256 hash of the canonical
    schema JSON.
    """

    if not canonical_schema_json:
        raise SchemaFingerprintError(
            message=(
                "Canonical schema JSON cannot "
                "be empty."
            ),
            guardrail_name=(
                "CANONICAL_SCHEMA_REQUIRED"
            ),
        )

    return hashlib.sha256(
        canonical_schema_json.encode(
            "utf-8"
        )
    ).hexdigest()


def generate_schema_fingerprint(
    workbook_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Build canonical schema JSON and calculate
    its deterministic SHA-256 fingerprint.
    """

    canonical_schema = (
        build_canonical_schema(
            workbook_metadata
        )
    )

    canonical_schema_json = (
        serialize_canonical_schema(
            canonical_schema
        )
    )

    schema_fingerprint = (
        calculate_schema_fingerprint(
            canonical_schema_json
        )
    )

    return {
        "fingerprint_version": (
            settings.fingerprint_version
        ),
        "fingerprint_algorithm": "SHA-256",
        "canonical_schema": (
            canonical_schema
        ),
        "canonical_schema_json": (
            canonical_schema_json
        ),
        "schema_fingerprint": (
            schema_fingerprint
        ),
        "guardrails": [
            {
                "name": (
                    "WORKBOOK_METADATA_REQUIRED"
                ),
                "status": "PASSED",
            },
            {
                "name": (
                    "NORMALIZED_SHEET_NAME_REQUIRED"
                ),
                "status": "PASSED",
            },
            {
                "name": (
                    "NORMALIZED_HEADERS_REQUIRED"
                ),
                "status": "PASSED",
            },
            {
                "name": (
                    "CANONICAL_SCHEMA_SERIALIZATION"
                ),
                "status": "PASSED",
            },
            {
                "name": (
                    "SHA256_SCHEMA_FINGERPRINT"
                ),
                "status": "PASSED",
            },
        ],
    }
