import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import (
    ParserDefinition,
    ParserVersion,
)


ALLOWED_TRANSFORMATIONS = {
    "identity",
    "trim",
    "upper",
    "lower",
    "parse_date",
    "parse_decimal",
}


class ParserRegistryError(ValueError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.guardrail_name = guardrail_name


def validate_schema_fingerprint(
    schema_fingerprint: str,
) -> None:
    if not isinstance(schema_fingerprint, str):
        raise ParserRegistryError(
            message="Schema fingerprint must be a string.",
            guardrail_name=(
                "VALID_SCHEMA_FINGERPRINT_REQUIRED"
            ),
        )

    if len(schema_fingerprint) != 64:
        raise ParserRegistryError(
            message=(
                "Schema fingerprint must contain "
                "64 hexadecimal characters."
            ),
            guardrail_name=(
                "VALID_SCHEMA_FINGERPRINT_REQUIRED"
            ),
        )

    try:
        int(schema_fingerprint, 16)
    except ValueError as exception:
        raise ParserRegistryError(
            message=(
                "Schema fingerprint must contain "
                "only hexadecimal characters."
            ),
            guardrail_name=(
                "VALID_SCHEMA_FINGERPRINT_REQUIRED"
            ),
        ) from exception


def validate_fingerprint_version(
    fingerprint_version: str,
) -> None:
    if (
        not isinstance(fingerprint_version, str)
        or not fingerprint_version.strip()
    ):
        raise ParserRegistryError(
            message="Fingerprint version is required.",
            guardrail_name=(
                "FINGERPRINT_VERSION_REQUIRED"
            ),
        )


def validate_canonical_schema_json(
    canonical_schema_json: str,
) -> None:
    if (
        not isinstance(canonical_schema_json, str)
        or not canonical_schema_json.strip()
    ):
        raise ParserRegistryError(
            message="Canonical schema JSON is required.",
            guardrail_name=(
                "CANONICAL_SCHEMA_REQUIRED"
            ),
        )

    try:
        parsed_schema = json.loads(
            canonical_schema_json
        )
    except json.JSONDecodeError as exception:
        raise ParserRegistryError(
            message=(
                "Canonical schema is not valid JSON."
            ),
            guardrail_name=(
                "VALID_CANONICAL_SCHEMA_REQUIRED"
            ),
        ) from exception

    if not isinstance(parsed_schema, dict):
        raise ParserRegistryError(
            message=(
                "Canonical schema must be a JSON object."
            ),
            guardrail_name=(
                "VALID_CANONICAL_SCHEMA_REQUIRED"
            ),
        )


def validate_parser_specification(
    parser_spec: dict[str, Any],
) -> None:
    if not isinstance(parser_spec, dict):
        raise ParserRegistryError(
            message=(
                "Parser specification must be "
                "a dictionary."
            ),
            guardrail_name=(
                "DECLARATIVE_PARSER_SPEC_REQUIRED"
            ),
        )

    allowed_top_level_fields = {
        "source_sheet",
        "header_row",
        "mappings",
        "assumptions",
        "description",
    }

    unsupported_fields = (
        set(parser_spec)
        - allowed_top_level_fields
    )

    if unsupported_fields:
        raise ParserRegistryError(
            message=(
                "Parser specification contains "
                "unsupported fields: "
                f"{sorted(unsupported_fields)}"
            ),
            guardrail_name=(
                "DECLARATIVE_FIELDS_ONLY"
            ),
        )

    source_sheet = parser_spec.get(
        "source_sheet"
    )

    if (
        not isinstance(source_sheet, str)
        or not source_sheet.strip()
    ):
        raise ParserRegistryError(
            message=(
                "Parser specification requires "
                "a non-empty source_sheet."
            ),
            guardrail_name=(
                "SOURCE_SHEET_REQUIRED"
            ),
        )

    header_row = parser_spec.get(
        "header_row"
    )

    if (
        not isinstance(header_row, int)
        or isinstance(header_row, bool)
        or not 1 <= header_row <= 100
    ):
        raise ParserRegistryError(
            message=(
                "Parser header_row must be an "
                "integer between 1 and 100."
            ),
            guardrail_name=(
                "VALID_HEADER_ROW_REQUIRED"
            ),
        )

    mappings = parser_spec.get("mappings")

    if (
        not isinstance(mappings, list)
        or not mappings
    ):
        raise ParserRegistryError(
            message=(
                "Parser specification requires "
                "at least one mapping."
            ),
            guardrail_name=(
                "PARSER_MAPPINGS_REQUIRED"
            ),
        )

    source_columns: set[str] = set()
    target_fields: set[str] = set()

    allowed_mapping_fields = {
        "source",
        "target",
        "transform",
        "required",
    }

    for index, mapping in enumerate(
        mappings,
        start=1,
    ):
        if not isinstance(mapping, dict):
            raise ParserRegistryError(
                message=(
                    "Invalid mapping at position "
                    f"{index}."
                ),
                guardrail_name=(
                    "VALID_MAPPING_REQUIRED"
                ),
            )

        unsupported_mapping_fields = (
            set(mapping)
            - allowed_mapping_fields
        )

        if unsupported_mapping_fields:
            raise ParserRegistryError(
                message=(
                    f"Mapping {index} contains "
                    "unsupported fields: "
                    f"{sorted(unsupported_mapping_fields)}"
                ),
                guardrail_name=(
                    "DECLARATIVE_FIELDS_ONLY"
                ),
            )

        source = mapping.get("source")
        target = mapping.get("target")
        transform = mapping.get("transform")
        required = mapping.get("required")

        if (
            not isinstance(source, str)
            or not source.strip()
        ):
            raise ParserRegistryError(
                message=(
                    "A source column is required "
                    f"at mapping {index}."
                ),
                guardrail_name=(
                    "SOURCE_COLUMN_REQUIRED"
                ),
            )

        if (
            not isinstance(target, str)
            or not target.strip()
        ):
            raise ParserRegistryError(
                message=(
                    "A target field is required "
                    f"at mapping {index}."
                ),
                guardrail_name=(
                    "TARGET_FIELD_REQUIRED"
                ),
            )

        if transform not in ALLOWED_TRANSFORMATIONS:
            raise ParserRegistryError(
                message=(
                    f"Transformation '{transform}' "
                    f"at mapping {index} is not "
                    "allowlisted."
                ),
                guardrail_name=(
                    "ALLOWLISTED_TRANSFORMATION_ONLY"
                ),
            )

        if not isinstance(required, bool):
            raise ParserRegistryError(
                message=(
                    "The required value must be "
                    f"boolean at mapping {index}."
                ),
                guardrail_name=(
                    "VALID_REQUIRED_FLAG"
                ),
            )

        normalized_source = source.strip()
        normalized_target = target.strip()

        if normalized_source in source_columns:
            raise ParserRegistryError(
                message=(
                    "Duplicate source column: "
                    f"{normalized_source}"
                ),
                guardrail_name=(
                    "UNIQUE_SOURCE_COLUMNS_REQUIRED"
                ),
            )

        if normalized_target in target_fields:
            raise ParserRegistryError(
                message=(
                    "Duplicate target field: "
                    f"{normalized_target}"
                ),
                guardrail_name=(
                    "UNIQUE_TARGET_FIELDS_REQUIRED"
                ),
            )

        source_columns.add(normalized_source)
        target_fields.add(normalized_target)


def deserialize_parser_specification(
    parser_spec_json: str,
) -> dict[str, Any]:
    try:
        parser_spec = json.loads(
            parser_spec_json
        )
    except json.JSONDecodeError as exception:
        raise ParserRegistryError(
            message=(
                "Stored parser specification "
                "is not valid JSON."
            ),
            guardrail_name=(
                "VALID_STORED_PARSER_SPEC"
            ),
        ) from exception

    validate_parser_specification(
        parser_spec
    )

    return parser_spec


def no_match_result() -> dict[str, Any]:
    return {
        "parser_match_found": False,
        "parser_execution_authorized": False,
        "parser_match_policy": (
            settings.parser_match_policy
        ),
        "matched_parser_id": None,
        "matched_parser_name": None,
        "matched_parser_version_id": None,
        "matched_parser_version_number": None,
        "matched_parser_spec": None,
        "matched_parser_approval_status": None,
        "matched_parser_status": None,
    }


def find_exact_approved_parser(
    database: Session,
    *,
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    validate_schema_fingerprint(
        schema_fingerprint
    )

    validate_fingerprint_version(
        fingerprint_version
    )

    statement = (
        select(
            ParserVersion,
            ParserDefinition,
        )
        .join(
            ParserDefinition,
            ParserVersion.parser_id
            == ParserDefinition.id,
        )
        .where(
            ParserVersion.schema_fingerprint
            == schema_fingerprint,
            ParserVersion.fingerprint_version
            == fingerprint_version.strip(),
            ParserVersion.status
            == "ACTIVE",
            ParserVersion.approval_status
            == "APPROVED",
            ParserDefinition.status
            == "ACTIVE",
        )
        .order_by(
            ParserVersion.version_number.desc()
        )
        .limit(1)
    )

    database_result = database.execute(
        statement
    ).first()

    if database_result is None:
        return no_match_result()

    parser_version = database_result[0]
    parser_definition = database_result[1]

    parser_spec = (
        deserialize_parser_specification(
            parser_version.parser_spec_json
        )
    )

    return {
        "parser_match_found": True,
        "parser_execution_authorized": True,
        "parser_match_policy": (
            settings.parser_match_policy
        ),
        "matched_parser_id": (
            parser_definition.id
        ),
        "matched_parser_name": (
            parser_definition.parser_name
        ),
        "matched_parser_version_id": (
            parser_version.id
        ),
        "matched_parser_version_number": (
            parser_version.version_number
        ),
        "matched_parser_spec": parser_spec,
        "matched_parser_approval_status": (
            parser_version.approval_status
        ),
        "matched_parser_status": (
            parser_version.status
        ),
    }


def register_bootstrap_approved_parser(
    database: Session,
    *,
    parser_name: str,
    description: str,
    schema_fingerprint: str,
    fingerprint_version: str,
    canonical_schema_json: str,
    parser_spec: dict[str, Any],
    created_by: str,
    approval_owner: str,
) -> dict[str, Any]:
    if (
        not isinstance(parser_name, str)
        or not parser_name.strip()
    ):
        raise ParserRegistryError(
            message="Parser name is required.",
            guardrail_name=(
                "PARSER_NAME_REQUIRED"
            ),
        )

    if (
        not isinstance(created_by, str)
        or not created_by.strip()
    ):
        raise ParserRegistryError(
            message="Parser creator is required.",
            guardrail_name=(
                "PARSER_CREATOR_REQUIRED"
            ),
        )

    if (
        not isinstance(approval_owner, str)
        or not approval_owner.strip()
    ):
        raise ParserRegistryError(
            message="Approval owner is required.",
            guardrail_name=(
                "APPROVAL_OWNER_REQUIRED"
            ),
        )

    validate_schema_fingerprint(
        schema_fingerprint
    )

    validate_fingerprint_version(
        fingerprint_version
    )

    validate_canonical_schema_json(
        canonical_schema_json
    )

    validate_parser_specification(
        parser_spec
    )

    existing_version = database.scalar(
        select(ParserVersion).where(
            ParserVersion.schema_fingerprint
            == schema_fingerprint,
            ParserVersion.fingerprint_version
            == fingerprint_version.strip(),
        )
    )

    if existing_version is not None:
        existing_parser = database.get(
            ParserDefinition,
            existing_version.parser_id,
        )

        return {
            "created": False,
            "parser_id": (
                existing_version.parser_id
            ),
            "parser_name": (
                existing_parser.parser_name
                if existing_parser is not None
                else parser_name.strip()
            ),
            "parser_version_id": (
                existing_version.id
            ),
            "version_number": (
                existing_version.version_number
            ),
            "status": existing_version.status,
            "approval_status": (
                existing_version.approval_status
            ),
        }

    parser_definition = database.scalar(
        select(ParserDefinition).where(
            ParserDefinition.parser_name
            == parser_name.strip()
        )
    )

    if parser_definition is None:
        parser_definition = ParserDefinition(
            id=str(uuid4()),
            parser_name=parser_name.strip(),
            description=description,
            status="ACTIVE",
            created_by=created_by.strip(),
        )

        database.add(parser_definition)
        database.flush()

    elif parser_definition.status != "ACTIVE":
        raise ParserRegistryError(
            message=(
                "Parser definition exists but "
                "is not active."
            ),
            guardrail_name=(
                "ACTIVE_PARSER_DEFINITION_REQUIRED"
            ),
        )

    latest_version_number = database.scalar(
        select(
            func.max(
                ParserVersion.version_number
            )
        ).where(
            ParserVersion.parser_id
            == parser_definition.id
        )
    )

    next_version_number = (
        int(latest_version_number or 0)
        + 1
    )

    parser_version = ParserVersion(
        id=str(uuid4()),
        parser_id=parser_definition.id,
        version_number=(
            next_version_number
        ),
        status="ACTIVE",
        approval_status="APPROVED",
        schema_fingerprint=(
            schema_fingerprint
        ),
        fingerprint_version=(
            fingerprint_version.strip()
        ),
        canonical_schema_json=(
            canonical_schema_json
        ),
        parser_spec_json=json.dumps(
            parser_spec,
            sort_keys=True,
            separators=(",", ":"),
        ),
        approval_owner=(
            approval_owner.strip()
        ),
        approved_at=datetime.now(UTC),
        created_by=created_by.strip(),
    )

    database.add(parser_version)
    database.flush()

    return {
        "created": True,
        "parser_id": parser_definition.id,
        "parser_name": (
            parser_definition.parser_name
        ),
        "parser_version_id": (
            parser_version.id
        ),
        "version_number": (
            parser_version.version_number
        ),
        "status": parser_version.status,
        "approval_status": (
            parser_version.approval_status
        ),
    }
