import json
import re
from datetime import datetime
from decimal import (
    Decimal,
    InvalidOperation,
)
from typing import Any

from app.core.config import settings
from app.services.parser_registry import (
    validate_parser_specification,
)


class OutputValidationError(ValueError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.guardrail_name = guardrail_name


def is_empty_value(
    value: Any,
) -> bool:
    if value is None:
        return True

    if (
        isinstance(value, str)
        and not value.strip()
    ):
        return True

    return False


def is_valid_iso_date(
    value: Any,
) -> bool:
    if is_empty_value(value):
        return True

    try:
        datetime.strptime(
            str(value),
            "%Y-%m-%d",
        )
        return True

    except ValueError:
        return False


def is_valid_decimal(
    value: Any,
) -> bool:
    if is_empty_value(value):
        return True

    if isinstance(value, bool):
        return False

    try:
        parsed_value = Decimal(
            str(value)
        )

        return parsed_value.is_finite()

    except (
        InvalidOperation,
        ValueError,
    ):
        return False


def is_valid_currency_code(
    value: Any,
) -> bool:
    if is_empty_value(value):
        return True

    return bool(
        re.fullmatch(
            r"[A-Z]{3}",
            str(value).strip(),
        )
    )


def canonical_record_key(
    record: dict[str, Any],
) -> str:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def determine_validation_status(
    *,
    error_count: int,
    warning_count: int,
) -> str:
    if error_count > 0:
        return "FAIL"

    if warning_count > 0:
        return "WARN"

    return "PASS"


def validate_parsed_records(
    *,
    parsed_records: list[dict[str, Any]],
    parser_spec: dict[str, Any],
    source_row_count: int,
    parsed_row_count: int,
    rejected_row_count: int,
    output_truncated: bool,
) -> dict[str, Any]:
    """
    Validate parser output deterministically.

    PASS:
        No errors or warnings.

    WARN:
        Output is structurally valid but contains
        non-blocking issues such as duplicates,
        suspicious currency values, or truncation.

    FAIL:
        Required fields are missing, required values
        are empty, typed values are invalid, or row
        counts are inconsistent.
    """

    validate_parser_specification(
        parser_spec
    )

    if not isinstance(
        parsed_records,
        list,
    ):
        raise OutputValidationError(
            message=(
                "Parsed output must be a list."
            ),
            guardrail_name=(
                "LIST_OUTPUT_REQUIRED"
            ),
        )

    if parsed_row_count != len(
        parsed_records
    ):
        raise OutputValidationError(
            message=(
                "Parsed row count does not match "
                "the number of parsed records."
            ),
            guardrail_name=(
                "PARSED_ROW_COUNT_CONSISTENCY"
            ),
        )

    if source_row_count < 0:
        raise OutputValidationError(
            message=(
                "Source row count cannot "
                "be negative."
            ),
            guardrail_name=(
                "VALID_SOURCE_ROW_COUNT"
            ),
        )

    if rejected_row_count < 0:
        raise OutputValidationError(
            message=(
                "Rejected row count cannot "
                "be negative."
            ),
            guardrail_name=(
                "VALID_REJECTED_ROW_COUNT"
            ),
        )

    required_mappings = [
        mapping
        for mapping
        in parser_spec["mappings"]
        if mapping["required"] is True
    ]

    target_mappings = {
        mapping["target"]: mapping
        for mapping
        in parser_spec["mappings"]
    }

    required_targets = {
        mapping["target"]
        for mapping in required_mappings
    }

    validation_issues: list[
        dict[str, Any]
    ] = []

    error_count = 0
    warning_count = 0
    missing_required_value_count = 0
    invalid_value_count = 0

    seen_records: dict[str, int] = {}
    duplicate_samples: list[
        dict[str, Any]
    ] = []
    duplicate_record_count = 0

    for record_index, record in enumerate(
        parsed_records,
        start=1,
    ):
        if not isinstance(record, dict):
            error_count += 1

            if (
                len(validation_issues)
                < settings
                .maximum_validation_issue_samples
            ):
                validation_issues.append(
                    {
                        "severity": "ERROR",
                        "code": (
                            "DICTIONARY_RECORD_REQUIRED"
                        ),
                        "record_number": (
                            record_index
                        ),
                        "field": None,
                        "message": (
                            "Parsed record must be "
                            "a dictionary."
                        ),
                    }
                )

            continue

        record_fields = set(
            record.keys()
        )

        missing_fields = sorted(
            required_targets
            - record_fields
        )

        for missing_field in missing_fields:
            error_count += 1
            missing_required_value_count += 1

            if (
                len(validation_issues)
                < settings
                .maximum_validation_issue_samples
            ):
                validation_issues.append(
                    {
                        "severity": "ERROR",
                        "code": (
                            "REQUIRED_FIELD_MISSING"
                        ),
                        "record_number": (
                            record_index
                        ),
                        "field": missing_field,
                        "message": (
                            "Required target field "
                            "is missing."
                        ),
                    }
                )

        for target_field, mapping in (
            target_mappings.items()
        ):
            if target_field not in record:
                continue

            value = record[target_field]

            if (
                mapping["required"] is True
                and is_empty_value(value)
            ):
                error_count += 1
                missing_required_value_count += 1

                if (
                    len(validation_issues)
                    < settings
                    .maximum_validation_issue_samples
                ):
                    validation_issues.append(
                        {
                            "severity": "ERROR",
                            "code": (
                                "REQUIRED_VALUE_EMPTY"
                            ),
                            "record_number": (
                                record_index
                            ),
                            "field": target_field,
                            "message": (
                                "Required value "
                                "is empty."
                            ),
                        }
                    )

                continue

            transformation = mapping[
                "transform"
            ]

            if (
                transformation
                == "parse_date"
                and not is_valid_iso_date(
                    value
                )
            ):
                error_count += 1
                invalid_value_count += 1

                if (
                    len(validation_issues)
                    < settings
                    .maximum_validation_issue_samples
                ):
                    validation_issues.append(
                        {
                            "severity": "ERROR",
                            "code": (
                                "INVALID_DATE_VALUE"
                            ),
                            "record_number": (
                                record_index
                            ),
                            "field": target_field,
                            "value": str(value),
                            "message": (
                                "Date value is not "
                                "in YYYY-MM-DD format."
                            ),
                        }
                    )

            if (
                transformation
                == "parse_decimal"
                and not is_valid_decimal(
                    value
                )
            ):
                error_count += 1
                invalid_value_count += 1

                if (
                    len(validation_issues)
                    < settings
                    .maximum_validation_issue_samples
                ):
                    validation_issues.append(
                        {
                            "severity": "ERROR",
                            "code": (
                                "INVALID_DECIMAL_VALUE"
                            ),
                            "record_number": (
                                record_index
                            ),
                            "field": target_field,
                            "value": str(value),
                            "message": (
                                "Value is not a "
                                "finite decimal."
                            ),
                        }
                    )

            normalized_field_name = (
                target_field.lower()
            )

            if (
                normalized_field_name
                in {
                    "currency",
                    "currency_code",
                    "payment_currency",
                    "settlement_currency",
                }
                and not is_valid_currency_code(
                    value
                )
            ):
                warning_count += 1

                if (
                    len(validation_issues)
                    < settings
                    .maximum_validation_issue_samples
                ):
                    validation_issues.append(
                        {
                            "severity": "WARNING",
                            "code": (
                                "SUSPICIOUS_CURRENCY_CODE"
                            ),
                            "record_number": (
                                record_index
                            ),
                            "field": target_field,
                            "value": str(value),
                            "message": (
                                "Currency value is not "
                                "a three-letter uppercase "
                                "code."
                            ),
                        }
                    )

        record_key = canonical_record_key(
            record
        )

        if record_key in seen_records:
            duplicate_record_count += 1
            warning_count += 1

            if (
                len(duplicate_samples)
                < settings
                .maximum_duplicate_samples
            ):
                duplicate_samples.append(
                    {
                        "record_number": (
                            record_index
                        ),
                        "first_record_number": (
                            seen_records[
                                record_key
                            ]
                        ),
                    }
                )

            if (
                len(validation_issues)
                < settings
                .maximum_validation_issue_samples
            ):
                validation_issues.append(
                    {
                        "severity": "WARNING",
                        "code": (
                            "DUPLICATE_RECORD"
                        ),
                        "record_number": (
                            record_index
                        ),
                        "field": None,
                        "message": (
                            "Parsed record duplicates "
                            "an earlier record."
                        ),
                    }
                )

        else:
            seen_records[
                record_key
            ] = record_index

    processed_row_count = (
        parsed_row_count
        + rejected_row_count
    )

    row_reconciliation_valid = (
        output_truncated
        or processed_row_count
        <= source_row_count
    )

    if not row_reconciliation_valid:
        error_count += 1

        if (
            len(validation_issues)
            < settings
            .maximum_validation_issue_samples
        ):
            validation_issues.append(
                {
                    "severity": "ERROR",
                    "code": (
                        "ROW_COUNT_RECONCILIATION_FAILED"
                    ),
                    "record_number": None,
                    "field": None,
                    "message": (
                        "Parsed and rejected row "
                        "counts exceed source rows."
                    ),
                }
            )

    if output_truncated:
        warning_count += 1

        if (
            len(validation_issues)
            < settings
            .maximum_validation_issue_samples
        ):
            validation_issues.append(
                {
                    "severity": "WARNING",
                    "code": (
                        "OUTPUT_TRUNCATED"
                    ),
                    "record_number": None,
                    "field": None,
                    "message": (
                        "Output reached the configured "
                        "maximum row limit."
                    ),
                }
            )

    validation_status = (
        determine_validation_status(
            error_count=error_count,
            warning_count=warning_count,
        )
    )

    completeness_percentage = (
        100.0
        if parsed_row_count == 0
        else round(
            (
                (
                    parsed_row_count
                    - missing_required_value_count
                )
                / parsed_row_count
            )
            * 100,
            2,
        )
    )

    uniqueness_percentage = (
        100.0
        if parsed_row_count == 0
        else round(
            (
                (
                    parsed_row_count
                    - duplicate_record_count
                )
                / parsed_row_count
            )
            * 100,
            2,
        )
    )

    valid_record_percentage = (
        100.0
        if parsed_row_count == 0
        else round(
            (
                (
                    parsed_row_count
                    - min(
                        parsed_row_count,
                        invalid_value_count,
                    )
                )
                / parsed_row_count
            )
            * 100,
            2,
        )
    )

    return {
        "validation_status": (
            validation_status
        ),
        "validation_summary": {
            "message": (
                "Parsed output passed validation."
                if validation_status == "PASS"
                else (
                    "Parsed output contains "
                    "non-blocking warnings."
                    if validation_status == "WARN"
                    else (
                        "Parsed output failed "
                        "validation."
                    )
                )
            ),
            "error_count": error_count,
            "warning_count": warning_count,
            "issue_sample_count": len(
                validation_issues
            ),
            "issue_samples_truncated": (
                (
                    error_count
                    + warning_count
                )
                > len(validation_issues)
            ),
            "row_reconciliation_valid": (
                row_reconciliation_valid
            ),
        },
        "validation_issues": (
            validation_issues
        ),
        "validation_metrics": {
            "source_row_count": (
                source_row_count
            ),
            "parsed_row_count": (
                parsed_row_count
            ),
            "rejected_row_count": (
                rejected_row_count
            ),
            "duplicate_record_count": (
                duplicate_record_count
            ),
            "missing_required_value_count": (
                missing_required_value_count
            ),
            "invalid_value_count": (
                invalid_value_count
            ),
            "completeness_percentage": (
                completeness_percentage
            ),
            "uniqueness_percentage": (
                uniqueness_percentage
            ),
            "valid_record_percentage": (
                valid_record_percentage
            ),
            "output_truncated": (
                output_truncated
            ),
            "duplicate_samples": (
                duplicate_samples
            ),
        },
        "duplicate_record_count": (
            duplicate_record_count
        ),
        "missing_required_value_count": (
            missing_required_value_count
        ),
        "invalid_value_count": (
            invalid_value_count
        ),
    }
